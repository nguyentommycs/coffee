import logging
from pydantic import BaseModel
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PREFERRED_DOMAINS = [
    "onyxcoffeelab.com",
    "bluebottlecoffee.com",
    "counterculturecoffee.com",
    "sweetbloomcoffee.com",
    "intelligentsia.com",
    "stumptown.com",
    "heartroasters.com",
]
BLOCKED_DOMAINS = ["amazon.com", "beanconqueror.com", "reddit.com", "coffeereview.com"]

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


async def web_search(query: str, n_results: int = 5) -> list[SearchResult]:
    """Search using Brave Search API. Returns [] with a warning if key is missing."""
    if not settings.brave_api_key:
        logger.warning("BRAVE_API_KEY not set; web_search returning empty results")
        return []

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            BRAVE_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": settings.brave_api_key,
            },
            params={"q": query, "count": n_results * 2},
            timeout=10,
        )
        resp.raise_for_status()

    data = resp.json()
    raw_results = [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("description", ""),
        )
        for r in data.get("web", {}).get("results", [])
    ]

    filtered = [r for r in raw_results if not any(d in r.url for d in BLOCKED_DOMAINS)]
    preferred = [r for r in filtered if any(d in r.url for d in PREFERRED_DOMAINS)]
    other = [r for r in filtered if r not in preferred]
    return (preferred + other)[:n_results]
