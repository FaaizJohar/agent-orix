"""
Knowledge Retriever querying local SQLite FTS5 index with BM25 relevance ranking.
"""

import re
from typing import List, Optional
from cie.knowledge.schemas import KnowledgeEvidencePackage, KnowledgeSearchResult
from cie.knowledge.store import KnowledgeStore

STOP_WORDS = {
    "what", "is", "the", "tell", "me", "about", "who", "are", "where",
    "how", "can", "you", "does", "do", "and", "or", "in", "of", "a", "an"
}


class KnowledgeRetriever:
    def __init__(self, store: Optional[KnowledgeStore] = None, max_chunks: int = 3):
        self.store = store or KnowledgeStore()
        self.max_chunks = max_chunks

    def normalize_query(self, query: str) -> str:
        """
        Extracts high-information keywords from natural language prompts.
        """
        words = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", query.lower())
        filtered = [w for w in words if w not in STOP_WORDS]
        return " ".join(filtered) if filtered else query.strip()

    def retrieve(
        self,
        query: str,
        collection: Optional[str] = None,
    ) -> KnowledgeEvidencePackage:
        warnings: List[str] = []
        normalized_q = self.normalize_query(query)

        if not normalized_q:
            return KnowledgeEvidencePackage(
                query=query,
                chunks=[],
                warnings=["Query contains no search keywords."],
            )

        # FTS5 search
        chunks = self.store.search_fts(normalized_q, collection=collection, limit=self.max_chunks)

        if not chunks:
            warnings.append(f"No local knowledge documents matched keywords: '{normalized_q}'.")

        return KnowledgeEvidencePackage(
            query=normalized_q,
            chunks=chunks,
            warnings=warnings,
        )
