"""
End-to-End Research Engine coordinating search, safe fetching, and citation verification.
"""

import re
import time
from typing import List, Optional
import urllib.parse

from cie.research.citations import CitationEngine
from cie.research.fetcher import SafeWebFetcher, SecurityValidationError, FetchLimitExceededError
from cie.research.provider import SearchProvider, DuckDuckGoHtmlProvider, SearchProviderError
from cie.research.schemas import EvidencePackage, ResearchResult, SearchResult, SourceRecord


FILLER_PREFIXES = [
    re.compile(r"^(search\s+the\s+web\s+(for\s+)?|browse\s+the\s+internet\s+(for\s+)?|google\s+|look\s+up\s+online\s+(for\s+)?)", re.IGNORECASE),
    re.compile(r"^(what\s+is\s+the\s+latest\s+on\s+|find\s+me\s+recent\s+news\s+about\s+)", re.IGNORECASE),
]


class ResearchEngine:
    def __init__(
        self,
        provider: Optional[SearchProvider] = None,
        fetcher: Optional[SafeWebFetcher] = None,
        max_search_results: int = 5,
        max_fetch_pages: int = 2,
    ):
        self.provider = provider or DuckDuckGoHtmlProvider()
        self.fetcher = fetcher or SafeWebFetcher()
        self.max_search_results = max_search_results
        self.max_fetch_pages = max_fetch_pages
        self.citation_engine = CitationEngine()

    def normalize_query(self, raw_prompt: str) -> str:
        """
        Strips conversational framing to produce an effective keyword search query.
        """
        cleaned = raw_prompt.strip()
        for pat in FILLER_PREFIXES:
            cleaned = pat.sub("", cleaned).strip()
        # Remove trailing punctuation like ?
        cleaned = re.sub(r"[?!.]+$", "", cleaned).strip()
        return cleaned or raw_prompt.strip()

    async def gather_evidence(self, query: str) -> EvidencePackage:
        """
        Executes search and fetches top eligible webpages, compiling a validated EvidencePackage.
        """
        warnings: List[str] = []
        normalized_q = self.normalize_query(query)

        # 1. Search Provider
        try:
            results = await self.provider.search(normalized_q, max_results=self.max_search_results)
        except SearchProviderError as e:
            return EvidencePackage(
                query=normalized_q,
                sources=[],
                warnings=[f"Search provider error: {str(e)}"],
            )

        if not results:
            return EvidencePackage(
                query=normalized_q,
                sources=[],
                warnings=[f"No search results found for query: '{normalized_q}'."],
            )

        # 2. Deduplicate URLs & filter
        seen_urls = set()
        deduped: List[SearchResult] = []
        for r in results:
            norm_url = r.url.lower().rstrip("/")
            if norm_url not in seen_urls:
                seen_urls.add(norm_url)
                deduped.append(r)

        # 3. Fetch Top Eligible Pages safely
        sources: List[SourceRecord] = []
        fetched_count = 0

        for idx, res in enumerate(deduped):
            if fetched_count >= self.max_fetch_pages:
                break

            source_id = f"Source {len(sources) + 1}"

            try:
                # Attempt safe fetch & extraction
                page_data = await self.fetcher.fetch(res.url)
                sources.append(
                    SourceRecord(
                        source_id=source_id,
                        url=page_data.get("final_url", res.url),
                        title=page_data.get("title") or res.title,
                        publication_date=page_data.get("publication_date") or res.date,
                        excerpt=page_data.get("text") or res.snippet,
                        provenance="web_page_fetch",
                        http_status=page_data.get("http_status", 200),
                    )
                )
                fetched_count += 1
            except (SecurityValidationError, FetchLimitExceededError) as e:
                # If full page fetch is blocked (e.g. SSRF or size) or fails, retain verified snippet
                warnings.append(f"Webpage fetch bypassed for '{res.url}': {str(e)}. Using verified search snippet.")
                sources.append(
                    SourceRecord(
                        source_id=source_id,
                        url=res.url,
                        title=res.title,
                        publication_date=res.date,
                        excerpt=res.snippet,
                        provenance="search_snippet_fallback",
                        http_status=200,
                    )
                )
                fetched_count += 1
            except Exception as e:
                warnings.append(f"Failed to fetch '{res.url}': {str(e)}. Using snippet.")
                sources.append(
                    SourceRecord(
                        source_id=source_id,
                        url=res.url,
                        title=res.title,
                        publication_date=res.date,
                        excerpt=res.snippet,
                        provenance="search_snippet_fallback",
                        http_status=200,
                    )
                )
                fetched_count += 1

        return EvidencePackage(
            query=normalized_q,
            sources=sources,
            warnings=warnings,
        )
