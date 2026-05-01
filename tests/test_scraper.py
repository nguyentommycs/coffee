import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.tools.scraper import scrape_page, scrape_roaster_catalog

SAMPLE_PRODUCT_HTML = """
<html>
<head><title>Geometry - Onyx Coffee Lab</title></head>
<body>
  <nav>Navigation</nav>
  <main>
    <h1 class="product__title">Geometry</h1>
    <div class="product__description">
      Single origin Ethiopian coffee from Yirgacheffe. Washed process.
      Tasting notes: jasmine, peach, Meyer lemon. Light roast.
    </div>
  </main>
  <footer>Footer content</footer>
  <script>var x = 1;</script>
</body>
</html>
"""

SAMPLE_GENERIC_CATALOG_HTML = """
<html><body>
  <a href="/products/ethiopian-blend">Ethiopian Blend</a>
  <a href="/products/colombia-huila">Colombia Huila</a>
  <a href="/about">About Us</a>
</body></html>
"""


def _mock_response(html: str, status: int = 200) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.text = html
    mock.status_code = status
    mock.raise_for_status = MagicMock()
    mock.json.side_effect = ValueError("not JSON")
    return mock


@pytest.mark.asyncio
async def test_scrape_page_extracts_main_content():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=_mock_response(SAMPLE_PRODUCT_HTML))

        result = await scrape_page("https://onyxcoffeelab.com/products/geometry")

    assert "jasmine" in result
    assert "peach" in result
    assert "Navigation" not in result
    assert "Footer content" not in result


@pytest.mark.asyncio
async def test_scrape_page_strips_scripts():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=_mock_response(SAMPLE_PRODUCT_HTML))

        result = await scrape_page("https://onyxcoffeelab.com/products/geometry")

    assert "var x" not in result


@pytest.mark.asyncio
async def test_scrape_page_truncates_to_12000_chars():
    long_html = "<main>" + ("x " * 10000) + "</main>"
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=_mock_response(long_html))

        result = await scrape_page("https://example.com/product")

    assert len(result) <= 12000


@pytest.mark.asyncio
async def test_scrape_page_returns_empty_on_http_error():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

        result = await scrape_page("https://example.com/product")

    assert result == ""


@pytest.mark.asyncio
async def test_scrape_roaster_catalog_generic_fallback():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(
            return_value=_mock_response(SAMPLE_GENERIC_CATALOG_HTML)
        )

        results = await scrape_roaster_catalog("https://unknownroaster.com/collections/all")

    urls = [r["url"] for r in results]
    assert any("/products/ethiopian-blend" in u for u in urls)
    assert any("/products/colombia-huila" in u for u in urls)
    # /about should be excluded
    assert all("/about" not in u for u in urls)

