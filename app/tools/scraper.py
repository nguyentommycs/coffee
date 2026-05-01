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

# Domain-specific CSS selectors for catalog pages: {item, name, price (optional)}
ROASTER_SELECTORS: dict[str, dict[str, str]] = {
    "onyxcoffeelab.com": {
        "item": ".product-item",
        "name": ".product-item__title",
        "price": ".product-item__price",
    },
}



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


def _build_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_shopify_products(products: list[dict], base_url: str) -> list[dict]:
    results = []
    for p in products:
        handle = p.get("handle")
        if not handle:
            continue
        prices = [v.get("price") for v in p.get("variants", []) if v.get("price")]
        min_price = min((_parse_price(pr) for pr in prices if pr), default=None)
        results.append({
            "name": p.get("title", handle),
            "url": f"{base_url}/products/{handle}",
            "price_usd": min_price,
        })
    return results


async def _try_shopify_json(client: httpx.AsyncClient, catalog_url: str) -> list[dict] | None:
    """
    Tries Shopify JSON endpoints. Returns parsed results or None if not a Shopify store.
    Tries collection-scoped endpoint first (preserves catalog filter), then site-wide.
    """
    parsed = urlparse(catalog_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Collection-scoped: /collections/<name> → /collections/<name>/products.json
    if "/collections/" in parsed.path:
        collection_path = parsed.path.rstrip("/")
        json_url = f"{base_url}{collection_path}/products.json?limit=250"
        try:
            resp = await client.get(json_url, headers={"User-Agent": USER_AGENT}, timeout=15, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("products", [])
                if products:
                    return _parse_shopify_products(products, base_url)
        except Exception:
            pass

    # Site-wide: /products.json, filter to coffee product types
    json_url = f"{base_url}/products.json?limit=250"
    try:
        resp = await client.get(json_url, headers={"User-Agent": USER_AGENT}, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            products = data.get("products")
            if products is not None:
                coffee_products = [
                    p for p in products
                    if "coffee" in p.get("product_type", "").lower()
                    or "coffee" in " ".join(p.get("tags", [])).lower()
                ]
                if coffee_products:
                    return _parse_shopify_products(coffee_products, base_url)
    except Exception:
        pass

    return None


async def scrape_roaster_catalog(catalog_url: str) -> list[dict]:
    """
    Scrapes a roaster's collection page.
    Returns list of dicts: {name, url, price_usd (or None)}.
    Tries Shopify JSON API first, then domain-specific CSS selectors, then generic link scraping.
    """
    async with httpx.AsyncClient() as client:
        shopify_results = await _try_shopify_json(client, catalog_url)
        if shopify_results is not None:
            return shopify_results

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
    base = _build_base_url(catalog_url)
    parsed_domain = urlparse(catalog_url).netloc.removeprefix("www.")
    selectors = ROASTER_SELECTORS.get(parsed_domain)

    if selectors:
        seen_urls: set[str] = set()
        results: list[dict] = []
        for item in soup.select(selectors["item"]):
            a = item.find("a", href=True)
            if not a:
                continue
            href: str = a["href"]
            if not href.startswith("http"):
                href = base + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            name_el = item.select_one(selectors["name"])
            name = name_el.get_text(strip=True) if name_el else a.get_text(strip=True)
            price_selector = selectors.get("price")
            price_el = item.select_one(price_selector) if price_selector else None
            price_usd = _parse_price(price_el.get_text(strip=True)) if price_el else None
            results.append({"name": name, "url": href, "price_usd": price_usd})
        return results

    seen_urls2: set[str] = set()
    results2: list[dict] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/products/" not in href:
            continue
        if not href.startswith("http"):
            href = base + href
        if href in seen_urls2:
            continue
        seen_urls2.add(href)
        results2.append({"name": a.get_text(strip=True) or href, "url": href, "price_usd": None})
    return results2
