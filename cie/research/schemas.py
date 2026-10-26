"""
Data models and schemas for CIE Research Subsystem.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    date: Optional[str] = None
    provider: str = "unknown"


class SourceRecord(BaseModel):
    source_id: str  # e.g. "Source 1"
    url: str
    title: str
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    publication_date: Optional[str] = None
    excerpt: str
    raw_text: Optional[str] = None
    provenance: str = "live_fetch"
    http_status: int = 200


class EvidencePackage(BaseModel):
    query: str
    sources: List[SourceRecord] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    warnings: List[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.sources) == 0


class ResearchResult(BaseModel):
    success: bool
    answer: str
    evidence: EvidencePackage
    verified_citations: List[str] = Field(default_factory=list)
    unverified_citations: List[str] = Field(default_factory=list)
    retrieval_duration_ms: float = 0.0
    synthesis_duration_ms: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None
