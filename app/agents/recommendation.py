"""
Recommendation Agent.

Given a TasteProfile, scrapes curated roaster catalog pages, extracts structured
details for all of a roaster's products via a single batched LLM call per roaster,
scores every candidate deterministically, and returns a ranked list of
RecommendationCandidate objects.

Cost ceiling: 1 LLM call per roaster in scope (plus a retry on invalid JSON).
Normal mode (broad_mode=False): 4 roasters = up to 8 LLM calls.
Broad mode (broad_mode=True):   8 roasters = up to 16 LLM calls.
"""
import asyncio
import json
import logging

from app.llm import llm_complete
from app.models.recommendation import CriticObjection, RecommendationCandidate
from app.observability.trace import child_span
from app.models.taste_profile import TasteProfile
from app.tools.scorer import score_candidate
from app.tools.scraper import scrape_page, scrape_roaster_catalog

logger = logging.getLogger(__name__)

CANDIDATES_PER_ROASTER = 10

# Per-product text budget inside a batched prompt — keeps a 10-product prompt
# a reasonable size even though scrape_page() itself returns up to 12 000 chars.
BATCH_ITEM_CHAR_LIMIT = 3000

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
You are a coffee data extraction specialist. Given scraped text from multiple product \
pages on {roaster}'s catalog, extract structured fields for EACH product below.

Return a JSON array with one object per product, in the same order given, each shaped as:

{{
  "url": string,
  "origin_country": string | null,
  "origin_region": string | null,
  "process": "Washed" | "Natural" | "Honey" | "Anaerobic" | null,
  "roast_level": "Light" | "Medium-Light" | "Medium" | "Dark" | null,
  "tasting_notes": string[],
  "in_stock": boolean | null
}}

Rules:
- "url" must exactly match the product's URL below, so results can be matched back.
- Only extract information explicitly present in the text. Do not infer or hallucinate.
- Normalize process names to: Washed, Natural, Honey, or Anaerobic.
- Normalize roast levels to: Light, Medium-Light, Medium, or Dark.
- Tasting notes should be lowercase, individual flavor descriptors (e.g., ["peach", "jasmine"]).
- in_stock: true if page indicates available/add-to-cart, false if sold-out/out-of-stock, null if unclear.
- Return exactly one object per product listed, even if a product has no extractable data (use nulls).
- Return only valid JSON. No preamble, no markdown fences.

Products:
{products_block}
"""

_OBJECTION_FILTER_PROMPT_TEMPLATE = """\
You are revising coffee recommendations after critic feedback. In a previous round, \
a critic rejected some candidates for these reasons:

{objections_block}

Below are {n_candidates} NEW candidate coffees (0-indexed):

{candidates_json}

Identify which of these new candidates would likely draw the SAME objections from the \
critic, so they can be excluded before re-review.

Return a JSON object:
{{
  "excluded_indices": [int, ...]
}}

Return only valid JSON. No preamble, no markdown fences.\
"""

_SCHEMA_REMINDER = (
    "\n\nIMPORTANT: Your previous response was not valid JSON. "
    "Return ONLY a valid JSON object matching the schema above. "
    "No preamble, no markdown fences."
)


def _parse_batch_response(raw: str) -> list[dict] | None:
    """Parses the extraction response, requiring a JSON array. Returns None on failure."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


async def _extract_roaster_candidates(
    roaster_name: str,
    items_with_text: list[tuple[dict, str]],
) -> dict[str, dict]:
    """
    Single batched LLM call covering every product for one roaster.
    Returns {product_url: extracted_fields}; missing/failed entries are simply absent.
    """
    products_block = "\n\n".join(
        f"### Product {i + 1}\n"
        f"Name: {item['name']}\n"
        f"URL: {item['url']}\n"
        f"Scraped text: {(text or '(no content retrieved)')[:BATCH_ITEM_CHAR_LIMIT]}"
        for i, (item, text) in enumerate(items_with_text)
    )
    prompt = _EXTRACT_PROMPT_TEMPLATE.format(roaster=roaster_name, products_block=products_block)

    raw = await llm_complete(prompt, span="recommendation_extract")
    parsed = _parse_batch_response(raw)
    if parsed is None:
        raw2 = await llm_complete(prompt + _SCHEMA_REMINDER, span="recommendation_extract_retry")
        parsed = _parse_batch_response(raw2)
        if parsed is None:
            logger.warning("Batched LLM extraction failed for %s after retry", roaster_name)
            return {}

    return {entry["url"]: entry for entry in parsed if entry.get("url")}


async def _filter_by_objections(
    candidates: list[RecommendationCandidate],
    objections: list[CriticObjection],
) -> list[RecommendationCandidate]:
    """
    One LLM call that drops new candidates likely to draw the same critic objections.
    Fails open: on invalid JSON, or if the filter would drop everything, the
    candidate list is returned unchanged.
    """
    objections_block = "\n".join(
        f"- {o.candidate_name} ({o.roaster}): {o.reason}" for o in objections
    )
    candidate_summaries = [
        {
            "index": i,
            "name": c.name,
            "roaster": c.roaster,
            "match_score": c.match_score,
            "match_rationale": c.match_rationale,
            "tasting_notes": c.tasting_notes,
        }
        for i, c in enumerate(candidates)
    ]
    prompt = _OBJECTION_FILTER_PROMPT_TEMPLATE.format(
        objections_block=objections_block,
        n_candidates=len(candidates),
        candidates_json=json.dumps(candidate_summaries, indent=2),
    )

    raw = await llm_complete(prompt, span="recommendation_revision_filter")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = await llm_complete(
            prompt + _SCHEMA_REMINDER, span="recommendation_revision_filter_retry"
        )
        try:
            data = json.loads(raw2)
        except json.JSONDecodeError:
            logger.warning("Objection filter returned invalid JSON after retry; keeping all candidates")
            return candidates

    excluded = {
        idx
        for idx in (data.get("excluded_indices") or [])
        if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(candidates)
    }
    kept = [c for i, c in enumerate(candidates) if i not in excluded]
    if not kept:
        logger.warning("Objection filter excluded every candidate; keeping all candidates")
        return candidates

    logger.info("Objection filter dropped %d/%d candidates", len(excluded), len(candidates))
    return kept


async def run(
    taste_profile: TasteProfile,
    n_recommendations: int = 5,
    broad_mode: bool = False,
    exclude_urls: set[str] | None = None,
    objections: list[CriticObjection] | None = None,
) -> list[RecommendationCandidate]:
    """
    Scrape roaster catalogs, extract and score candidates, return top n_recommendations*2.

    broad_mode=True scrapes all 8 roasters; default scrapes the first 4.
    exclude_urls drops catalog items already reviewed in an earlier round.
    objections triggers one LLM filter pass that removes candidates likely to
    draw the same critic objections.
    Returns candidates sorted by match_score descending, capped at n_recommendations * 2.
    """
    roasters = ROASTERS if broad_mode else ROASTERS[:4]
    logger.info("Starting recommendation run (broad_mode=%s, %d roasters)", broad_mode, len(roasters))

    candidates: list[RecommendationCandidate] = []
    for roaster_name, catalog_url in roasters:
        items = await scrape_roaster_catalog(catalog_url)
        logger.info("  %s: %d catalog items found", roaster_name, len(items))
        items = [it for it in items[:CANDIDATES_PER_ROASTER] if it.get("url") and it.get("name")]
        if exclude_urls:
            items = [it for it in items if str(it["url"]) not in exclude_urls]
        if not items:
            continue

        page_texts = await asyncio.gather(*[scrape_page(it["url"]) for it in items])
        details_by_url = await _extract_roaster_candidates(roaster_name, list(zip(items, page_texts)))

        for item in items:
            details = details_by_url.get(item["url"], {})
            try:
                candidates.append(
                    RecommendationCandidate(
                        name=item["name"],
                        roaster=roaster_name,
                        product_url=item["url"],
                        origin_country=details.get("origin_country"),
                        origin_region=details.get("origin_region"),
                        process=details.get("process"),
                        roast_level=details.get("roast_level"),
                        tasting_notes=details.get("tasting_notes") or [],
                        price_usd=item.get("price_usd"),
                        in_stock=details.get("in_stock"),
                    )
                )
            except Exception as exc:
                logger.warning("Failed to build RecommendationCandidate for %s: %s", item["url"], exc)

    if not candidates:
        logger.warning("No catalog items found across all roasters")
        return []

    logger.info(
        "%d candidates extracted across %d roasters via %d batched LLM calls",
        len(candidates), len(roasters), len(roasters),
    )

    with child_span("score_candidates", type="tool", candidates_scored=len(candidates)):
        for candidate in candidates:
            candidate_dict = {
                "origin_country": candidate.origin_country,
                "process": candidate.process,
                "roast_level": candidate.roast_level,
                "tasting_notes": candidate.tasting_notes,
            }
            score, rationale, breakdown = score_candidate(candidate_dict, taste_profile)
            candidate.match_score = score
            candidate.match_rationale = rationale
            candidate.score_breakdown = breakdown

    candidates.sort(key=lambda c: c.match_score, reverse=True)

    if objections:
        candidates = await _filter_by_objections(candidates, objections)

    top = candidates[: n_recommendations * 2]
    logger.info(
        "Returning %d candidates, scores: %s",
        len(top),
        [round(c.match_score, 2) for c in top],
    )
    return top
