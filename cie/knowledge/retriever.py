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

    def _rerank_chunks(self, query: str, chunks: List[KnowledgeSearchResult]) -> List[KnowledgeSearchResult]:
        """
        Domain-aware reranking to maintain strict identity distinction between
        the parent technology company (Cavrix Core) and the AI coding assistant (Cavrix Code).
        """
        q_lower = query.lower()
        is_cavrix_core = (
            "cavrix core" in q_lower
            or (("who" in q_lower or "founder" in q_lower or "company" in q_lower or "about" in q_lower or "mission" in q_lower) and "cavrix" in q_lower and "code" not in q_lower)
        )
        is_cavrix_code = "cavrix code" in q_lower or "coding assistant" in q_lower or "model" in q_lower or "parameter" in q_lower

        def score_chunk(chunk: KnowledgeSearchResult) -> float:
            base_score = chunk.score  # BM25 rank in SQLite FTS5 is negative (lower = better)
            adjustment = 0.0
            title_lower = chunk.title.lower()
            source_lower = chunk.source_path.lower()
            content_lower = chunk.content.lower()

            if is_cavrix_core:
                # Strongly boost official company profile overview & leadership chunk
                if "cavrix_core_profile" in source_lower or "official company profile" in title_lower:
                    if "leadership" in content_lower or "overview" in content_lower or "mission" in content_lower:
                        adjustment -= 150.0  # Decisive top priority for company profile
                    else:
                        adjustment -= 40.0
                # Heavily penalize model specifications and coding benchmarks when asking about the parent company
                if "model specifications" in title_lower or "evaluation summary" in title_lower or "dual-stack" in title_lower or "runtime & hardware" in title_lower:
                    adjustment += 100.0
            elif is_cavrix_code:
                # Strongly boost Cavrix Code model specs and technical provenance
                if "specifications" in title_lower or "cavrix code" in title_lower:
                    adjustment -= 60.0
                # Demote pure company profile overview when specifically asking about the coding assistant
                if "official company profile" in title_lower and "cavrix code" not in content_lower:
                    adjustment += 30.0

            return base_score + adjustment

        return sorted(chunks, key=score_chunk)

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

        # FTS5 search with expanded candidate window for reranking
        candidate_limit = max(10, self.max_chunks * 3)
        raw_chunks = self.store.search_fts(normalized_q, collection=collection, limit=candidate_limit)

        if not raw_chunks:
            warnings.append(f"No local knowledge documents matched keywords: '{normalized_q}'.")
            return KnowledgeEvidencePackage(
                query=normalized_q,
                chunks=[],
                warnings=warnings,
            )

        # Apply domain-aware reranking to enforce identity separation
        reranked = self._rerank_chunks(query, raw_chunks)
        selected_chunks = reranked[:self.max_chunks]

        return KnowledgeEvidencePackage(
            query=normalized_q,
            chunks=selected_chunks,
            warnings=warnings,
        )
