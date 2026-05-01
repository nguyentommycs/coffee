import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; CoffeeAgentBot/1.0; +https://github.com/nguyentommycs/coffee-agent)"
)

PRIORITY_SELECTORS = [
    ".product-description",
    ".product__description",
    "[data-product-description]",
    ".product-single__description",
    ".rte",
    "article",
    "main",
]

# CSS selectors per known roaster domain.  Each entry has:
#   item   – selector for a product card element
#   name   – selector for title within that card
#   url    – selector for the <a> link within that card
#   price  – selector for price within that card (optional, may be absent)
ROASTER_SELECTORS: dict[str, dict[str, str]] = {
    "onyxcoffeelab.com": {
        "item": ".product-item",
        "name": ".product-item__title",
        "url": "a",
        "price": ".product-item__price",
    },
    "bluebottlecoffee.com": {
        "item": "[data-test='product-card']",
        "name": "[data-test='product-name']",
        "url": "a",
        "price": "[data-test='product-price']",
    },
    "counterculturecoffee.com": {
        "item": ".product-card",
        "name": ".product-card__title",
        "url": "a",
        "price": ".product-card__price",
    },
}


def _extract_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.lstrip("www.")


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    import re
    m = re.search(r"\d+\.?\d*", text.replace(",", ""))
    return float(m.group()) if m else None


async def scrape_page(url: str) -> str:
    """Fetches URL, strips HTML, returns cleaned product text (max ~12 000 chars)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=10, follow_redirects=True
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("scrape_page failed for %s: %s", url, exc)
            return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    content = ""
    for selector in PRIORITY_SELECTORS:
        el = soup.select_one(selector)
        if el:
            content = el.get_text(separator=" ", strip=True)
            break

    if not content:
        content = soup.get_text(separator=" ", strip=True)

    return content[:12000]


async def scrape_roaster_catalog(catalog_url: str) -> list[dict]:
    """
    Scrapes a roaster's collection page.
    Returns list of dicts: {name, url, price_usd (or None)}.
    Uses domain-specific selectors when available, falls back to generic <a href*=/products/>.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                catalog_url,
                headers={"User-Agent": USER_AGENT},
                timeout=15,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("scrape_roaster_catalog failed for %s: %s", catalog_url, exc)
            return []

    soup = BeautifulSoup(resp.text, "html.parser")
    domain = _extract_domain(catalog_url)
    selectors = ROASTER_SELECTORS.get(domain)

    results: list[dict] = []

    if selectors:
        for item in soup.select(selectors["item"]):
            name_el = item.select_one(selectors["name"])
            url_el = item.select_one(selectors["url"])
            price_el = item.select_one(selectors.get("price", ""))

            if not name_el or not url_el:
                continue

            href = url_el.get("href", "")
            if href and not href.startswith("http"):
                base = f"{urlparse(catalog_url).scheme}://{urlparse(catalog_url).netloc}"
                href = base + href

            results.append(
                {
                    "name": name_el.get_text(strip=True),
                    "url": href,
                    "price_usd": _parse_price(price_el.get_text(strip=True) if price_el else None),
                }
            )
    else:
        # Generic fallback: collect <a> links whose href contains /products/
        seen_urls: set[str] = set()
        for a in soup.find_all("a", href=True):
            href: str = a["href"]
            if "/products/" not in href:
                continue
            if not href.startswith("http"):
                base = f"{urlparse(catalog_url).scheme}://{urlparse(catalog_url).netloc}"
                href = base + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            results.append(
                {
                    "name": a.get_text(strip=True) or href,
                    "url": href,
                    "price_usd": None,
                }
            )

    return results
