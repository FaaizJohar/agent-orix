"""
Search Provider Abstraction and Implementations for CIE.
"""

from abc import ABC, abstractmethod
import urllib.parse
from typing import List, Optional, Dict, Any
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from cie.research.schemas import SearchResult


class SearchProviderError(Exception):
    pass


class ProviderUnavailableError(SearchProviderError):
    pass


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Executes a web search query and returns structured SearchResult objects.
        """
        pass


class DuckDuckGoHtmlProvider(SearchProvider):
    """
    Direct HTML scraper for DuckDuckGo public HTML endpoint.
    Zero-key, privacy-preserving, non-JavaScript.
    """
    ENDPOINT = "https://html.duckduckgo.com/html/"
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        clean_query = query.strip()
        if not clean_query:
            return []

        payload = {"q": clean_query}

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(self.ENDPOINT, data=payload, headers=self.DEFAULT_HEADERS)

                if resp.status_code == 429 or resp.status_code == 202:
                    raise ProviderUnavailableError("DuckDuckGo HTML search rate-limited or throttling requests.")
                if resp.status_code != 200:
                    raise SearchProviderError(f"DuckDuckGo returned HTTP {resp.status_code}")

                if BeautifulSoup is None:
                    raise SearchProviderError("bs4 is required for HTML parsing but not installed.")
                soup = BeautifulSoup(resp.text, "html.parser")
                results: List[SearchResult] = []

                for div in soup.find_all("div", class_="result"):
                    if len(results) >= max_results:
                        break

                    title_tag = div.find("a", class_="result__a")
                    snippet_tag = div.find("a", class_="result__snippet")

                    if not title_tag or not snippet_tag:
                        continue

                    raw_href = title_tag.get("href", "")
                    clean_url = raw_href
                    if "uddg=" in raw_href:
                        parsed = urllib.parse.urlparse(raw_href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if "uddg" in qs and qs["uddg"]:
                            clean_url = qs["uddg"][0]

                    # Filter out DDG internal navigation links
                    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
                        continue

                    title_text = title_tag.get_text(strip=True)
                    snippet_text = snippet_tag.get_text(strip=True)

                    results.append(
                        SearchResult(
                            title=title_text,
                            url=clean_url,
                            snippet=snippet_text,
                            provider="duckduckgo_html",
                        )
                    )

                return results

        except httpx.TimeoutException as e:
            raise SearchProviderError(f"Search request timed out after {self.timeout}s.") from e
        except httpx.ConnectError as e:
            raise ProviderUnavailableError(f"Cannot connect to search provider: {e}") from e
        except SearchProviderError:
            raise
        except Exception as e:
            raise SearchProviderError(f"Search processing failed: {str(e)}") from e


class MockSearchProvider(SearchProvider):
    """
    Deterministic mock provider for offline and reproducible unit testing.
    """
    def __init__(self, predefined_results: Optional[Dict[str, List[SearchResult]]] = None):
        self.predefined_results = predefined_results or {}
        self.call_history: List[str] = []

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        self.call_history.append(query)
        results = self.predefined_results.get(query, [])
        return results[:max_results]
