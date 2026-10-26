"""
Data schemas for CIE Knowledge & Memory Subsystem.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class Document(BaseModel):
    id: Optional[int] = None
    collection: str = "default"
    source_path: str
    title: str
    content_hash: str
    size_bytes: int
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    id: Optional[int] = None
    document_id: int
    chunk_index: int
    chunk_identifier: str  # e.g. "Doc 1 - Chunk 0"
    title: str
    content: str
    token_estimate: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KnowledgeSearchResult(BaseModel):
    chunk_identifier: str
    title: str
    source_path: str
    collection: str
    content: str
    score: float = 0.0


class MemoryEntry(BaseModel):
    id: Optional[int] = None
    key: str
    value: str
    category: str = "project_fact"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KnowledgeEvidencePackage(BaseModel):
    query: str
    chunks: List[KnowledgeSearchResult] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    warnings: List[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.chunks) == 0
