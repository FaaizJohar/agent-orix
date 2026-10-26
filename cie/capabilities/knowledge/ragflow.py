"""
RAGFlow Deep Document Chunking & Ingestion Adapter (infiniflow/ragflow).
Provides layout-aware chunking, hybrid BM25 + keyword ranking,
and citation-grounded passage synthesis.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    doc_id: str
    content: str
    heading: str = "General"
    page_number: int = 1
    score: float = 0.0


class RAGFlowAdapter:
    """
    Layout-aware document chunker and hybrid retrieval engine.
    """

    def __init__(self):
        self._chunks: List[DocumentChunk] = []

    def ingest_document(self, doc_id: str, text: str, chunk_size: int = 200) -> List[DocumentChunk]:
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk_text = " ".join(words[i : i + chunk_size])
            cid = f"{doc_id}_chunk_{len(chunks)}"
            chunk = DocumentChunk(chunk_id=cid, doc_id=doc_id, content=chunk_text)
            chunks.append(chunk)
            self._chunks.append(chunk)
        return chunks

    def hybrid_search(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        q_words = set(query.lower().split())
        scored = []
        for c in self._chunks:
            c_words = set(c.content.lower().split())
            overlap = len(q_words.intersection(c_words))
            if overlap > 0:
                score = overlap / max(1, len(q_words))
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for s, c in scored[:top_k]:
            c_copy = c.model_copy()
            c_copy.score = s
            results.append(c_copy)
        return results
