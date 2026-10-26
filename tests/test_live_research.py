"""
Live-network integration tests for CIE Research Subsystem.
Requires active internet connection and live search endpoint reachability.
"""

import pytest
from cie.research.engine import ResearchEngine
from cie.research.provider import DuckDuckGoHtmlProvider
from cie.research.fetcher import SafeWebFetcher


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_duckduckgo_search():
    provider = DuckDuckGoHtmlProvider()
    try:
        results = await provider.search("python documentation official", max_results=3)
    except Exception as e:
        pytest.skip(f"Live search endpoint unavailable or throttled: {e}")

    if not results:
        pytest.skip("DuckDuckGo HTML endpoint returned 0 results.")
    assert len(results) > 0
    assert any("python.org" in r.url.lower() for r in results)


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_safe_fetcher():
    fetcher = SafeWebFetcher()
    try:
        result = await fetcher.fetch("https://example.com")
    except Exception as e:
        pytest.skip(f"Live network or DNS unavailable: {e}")

    assert result["http_status"] == 200
    assert "Example Domain" in result["title"]
    assert len(result["text"]) > 20
