"""
Recommendation Agent.

Given a TasteProfile, scrapes curated roaster catalog pages, extracts structured
details from each product page via a single LLM call, scores every candidate
deterministically, and returns a ranked list of RecommendationCandidate objects.

Cost ceiling: CANDIDATES_PER_ROASTER × roasters in scope LLM calls per run.
Normal mode (broad_mode=False): 4 roasters × 10 items = up to 40 LLM calls.
Broad mode (broad_mode=True):   8 roasters × 10 items = up to 80 LLM calls.
"""
import asyncio
import json
import logging

from app.llm import llm_complete
from app.models.recommendation import RecommendationCandidate
from app.models.taste_profile import TasteProfile
from app.tools.scorer import score_candidate
from app.tools.scraper import scrape_page, scrape_roaster_catalog

logger = logging.getLogger(__name__)

CANDIDATES_PER_ROASTER = 10

# Single source of truth: (display_name, catalog_url)
ROASTERS: list[tuple[str, str]] = [
    ("Onyx Coffee Lab",        "https://onyxcoffeelab.com/collections/coffee"),
    ("Blue Bottle Coffee",     "https://bluebottlecoffee.com/us/eng/collection/single-origin"),
    ("Counter Culture Coffee", "https://counterculturecoffee.com/collections/single-origins"),
    ("Intelligentsia",         "https://www.intelligentsia.com/collections/single-origins"),
    ("Black & White Coffee",   "https://www.blackwhiteroasters.com/collections/all-coffee"),
    ("Verve Coffee",           "https://www.vervecoffee.com/collections/all-coffee?filter.p.m.custom.type_=Single+Origin"),
    ("Sightglass Roasters",    "https://sightglasscoffee.com/collections/single-origin"),
    ("Sey Coffee",             "https://www.seycoffee.com/collections/coffee"),
]

_EXTRACT_PROMPT_TEMPLATE = """\
You are a coffee data extraction specialist. Given scraped text from a coffee \
roaster's product page, extract the following fields into a JSON object:

{{
  "origin_country": string | null,
  "origin_region": string | null,
  "process": "Washed" | "Natural" | "Honey" | "Anaerobic" | null,
  "roast_level": "Light" | "Medium-Light" | "Medium" | "Dark" | null,
  "tasting_notes": string[],
  "in_stock": boolean | null
}}

Rules:
- Only extract information explicitly present in the text. Do not infer or hallucinate.
- Normalize process names to: Washed, Natural, Honey, or Anaerobic.
- Normalize roast levels to: Light, Medium-Light, Medium, or Dark.
- Tasting notes should be lowercase, individual flavor descriptors (e.g., ["peach", "jasmine"]).
- in_stock: true if page indicates available/add-to-cart, false if sold-out/out-of-stock, null if unclear.
- Return only valid JSON. No preamble, no markdown fences.

Product name: {name}
Roaster: {roaster}
URL: {url}

Scraped text:
{text}
"""

_SCHEMA_REMINDER = (
    "\n\nIMPORTANT: Your previous response was not valid JSON. "
    "Return ONLY a valid JSON object matching the schema above. "
    "No preamble, no markdown fences."
)


async def _extract_candidate_details(
    name: str,
    url: str,
    roaster: str,
    page_text: str,
) -> dict:
    """LLM extraction of structured details from a product page. Returns {} on failure."""
    prompt = _EXTRACT_PROMPT_TEMPLATE.format(
        name=name,
        roaster=roaster,
        url=url,
        text=page_text or "(no content retrieved)",
    )
    raw = await llm_complete(prompt, span="recommendation_extract")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw2 = await llm_complete(prompt + _SCHEMA_REMINDER, span="recommendation_extract_retry")
        try:
            return json.loads(raw2)
        except json.JSONDecodeError:
            logger.warning("LLM extraction failed for %s after retry", url)
            return {}


async def _process_catalog_item(
    item: dict,
    roaster_name: str,
) -> RecommendationCandidate | None:
    """Scrape a product page, extract details, and build a RecommendationCandidate."""
    url: str = item.get("url") or ""
    name: str = item.get("name") or ""
    if not url or not name:
        return None

    logger.debug("Extracting details for %s – %s", roaster_name, name)
    page_text = await scrape_page(url)
    details = await _extract_candidate_details(name, url, roaster_name, page_text)

    try:
        return RecommendationCandidate(
            name=name,
            roaster=roaster_name,
            product_url=url,
            origin_country=details.get("origin_country"),
            origin_region=details.get("origin_region"),
            process=details.get("process"),
            roast_level=details.get("roast_level"),
            tasting_notes=details.get("tasting_notes") or [],
            price_usd=item.get("price_usd"),
            in_stock=details.get("in_stock"),
        )
    except Exception as exc:
        logger.warning("Failed to build RecommendationCandidate for %s: %s", url, exc)
        return None


async def run(
    taste_profile: TasteProfile,
    n_recommendations: int = 5,
    broad_mode: bool = False,
) -> list[RecommendationCandidate]:
    """
    Scrape roaster catalogs, extract and score candidates, return top n_recommendations*2.

    broad_mode=True scrapes all 8 roasters; default scrapes the first 4.
    Returns candidates sorted by match_score descending, capped at n_recommendations * 2.
    """
    roasters = ROASTERS if broad_mode else ROASTERS[:4]
    logger.info("Starting recommendation run (broad_mode=%s, %d roasters)", broad_mode, len(roasters))

    catalog_items: list[tuple[dict, str]] = []
    for roaster_name, catalog_url in roasters:
        items = await scrape_roaster_catalog(catalog_url)
        logger.info("  %s: %d catalog items found", roaster_name, len(items))
        for item in items[:CANDIDATES_PER_ROASTER]:
            catalog_items.append((item, roaster_name))

    if not catalog_items:
        logger.warning("No catalog items found across all roasters")
        return []

    catalog_items = catalog_items[:15]
    logger.info("Processing %d candidates via LLM extraction", len(catalog_items))
    tasks = [_process_catalog_item(item, roaster_name) for item, roaster_name in catalog_items]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    candidates: list[RecommendationCandidate] = []
    for result in results:
        if isinstance(result, RecommendationCandidate):
            candidates.append(result)
        elif isinstance(result, Exception):
            logger.warning("Candidate processing raised: %s", result)

    logger.info("%d/%d candidates extracted successfully", len(candidates), len(catalog_items))

    for candidate in candidates:
        candidate_dict = {
            "origin_country": candidate.origin_country,
            "process": candidate.process,
            "roast_level": candidate.roast_level,
            "tasting_notes": candidate.tasting_notes,
        }
        score, rationale = score_candidate(candidate_dict, taste_profile)
        candidate.match_score = score
        candidate.match_rationale = rationale

    candidates.sort(key=lambda c: c.match_score, reverse=True)
    top = candidates[: n_recommendations * 2]
    logger.info(
        "Returning %d candidates, scores: %s",
        len(top),
        [round(c.match_score, 2) for c in top],
    )
    return top
