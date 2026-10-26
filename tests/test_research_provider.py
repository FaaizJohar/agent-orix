"""
Tests for SearchProvider implementations and DuckDuckGo parsing.
"""

import pytest
from cie.research.provider import MockSearchProvider, DuckDuckGoHtmlProvider
from cie.research.schemas import SearchResult


@pytest.mark.asyncio
async def test_mock_search_provider():
    mock_results = {
        "python 3.14": [
            SearchResult(title="Python 3.14 Alpha", url="https://python.org/3.14", snippet="Latest alpha release."),
            SearchResult(title="What's New in 3.14", url="https://docs.python.org/3.14", snippet="Changelog details."),
        ]
    }
    provider = MockSearchProvider(predefined_results=mock_results)
    res = await provider.search("python 3.14", max_results=5)
    assert len(res) == 2
    assert res[0].title == "Python 3.14 Alpha"
    assert res[0].url == "https://python.org/3.14"
    assert provider.call_history == ["python 3.14"]


@pytest.mark.asyncio
async def test_mock_search_empty():
    provider = MockSearchProvider()
    res = await provider.search("unknown query 12345")
    assert res == []


@pytest.mark.asyncio
async def test_ddg_empty_query():
    provider = DuckDuckGoHtmlProvider()
    res = await provider.search("   ")
    assert res == []
