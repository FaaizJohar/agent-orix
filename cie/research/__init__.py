"""
Cavrix Intelligence Engine (CIE) - Research Subsystem
"""

from cie.research.schemas import SearchResult, SourceRecord, EvidencePackage, ResearchResult
from cie.research.provider import SearchProvider, DuckDuckGoHtmlProvider, MockSearchProvider
from cie.research.fetcher import SafeWebFetcher
from cie.research.citations import CitationEngine
from cie.research.engine import ResearchEngine

__all__ = [
    "SearchResult",
    "SourceRecord",
    "EvidencePackage",
    "ResearchResult",
    "SearchProvider",
    "DuckDuckGoHtmlProvider",
    "MockSearchProvider",
    "SafeWebFetcher",
    "CitationEngine",
    "ResearchEngine",
]
