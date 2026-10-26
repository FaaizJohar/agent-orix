"""
In-memory FTS5-based Retrieval Engine for Document Intelligence.
Provides zero-dependency, low-latency, BM25-ranked chunk retrieval within RAM bounds.
"""

import re
import sqlite3
from typing import List, Optional, Tuple

from cie.documents.schemas import DocumentChunk


class DocumentRetriever:
    """
    Indexes document chunks into an in-memory SQLite FTS5 database
    for accurate, traceable BM25 search without needing a heavy vector database.
    """

    def __init__(self, chunks: List[DocumentChunk]):
        self.chunks = chunks
        self.chunk_map = {c.chunk_id: c for c in chunks}
        self.conn = sqlite3.connect(":memory:")
        self._init_fts()

    def _init_fts(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id UNINDEXED,
                page_num UNINDEXED,
                section_title,
                content,
                tokenize='porter unicode61'
            );
            """
        )
        for c in self.chunks:
            cur.execute(
                """
                INSERT INTO chunks_fts(chunk_id, page_num, section_title, content)
                VALUES (?, ?, ?, ?);
                """,
                (
                    c.chunk_id,
                    str(c.page_number or ""),
                    c.section_title or "",
                    c.content,
                ),
            )
        self.conn.commit()

    def _clean_query(self, query: str) -> str:
        """Sanitizes search query for safe FTS5 MATCH evaluation."""
        words = re.findall(r"\w+", query)
        # Filter out common stop words
        stop_words = {"the", "is", "at", "which", "on", "a", "an", "and", "or", "in", "what", "where", "how", "who", "when"}
        filtered = [w for w in words if w.lower() not in stop_words and len(w) > 1]
        if not filtered:
            filtered = words
        return " OR ".join(f'"{w}"' for w in filtered[:10])

    def retrieve(self, query: str, max_chunks: int = 4) -> List[Tuple[DocumentChunk, float]]:
        """
        Retrieves top relevant chunks for the given question.
        Returns: List of (DocumentChunk, score)
        """
        if not self.chunks:
            return []

        fts_query = self._clean_query(query)
        if not fts_query:
            # Fallback to returning the first chunk if query has no tokens
            return [(self.chunks[0], 0.1)]

        cur = self.conn.cursor()
        results: List[Tuple[DocumentChunk, float]] = []

        try:
            cur.execute(
                """
                SELECT chunk_id, bm25(chunks_fts) as score
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY score ASC
                LIMIT ?;
                """,
                (fts_query, max_chunks),
            )
            for row in cur.fetchall():
                c_id, score = row[0], abs(float(row[1]))
                if c_id in self.chunk_map:
                    results.append((self.chunk_map[c_id], score))
        except sqlite3.OperationalError:
            # Fallback simple substring search if FTS syntax error occurs
            q_lower = query.lower()
            scored = []
            for c in self.chunks:
                c_lower = c.content.lower()
                overlap = sum(1 for w in query.split() if w.lower() in c_lower)
                if overlap > 0:
                    scored.append((c, float(overlap)))
            scored.sort(key=lambda x: x[1], reverse=True)
            results = scored[:max_chunks]

        return results

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
