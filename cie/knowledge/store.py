"""
SQLite FTS5 Storage Engine and Memory Manager for CIE.
Provides versioned schema migrations, transactions, and full-text search.
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cie.config import get_config
from cie.knowledge.schemas import Document, DocumentChunk, KnowledgeSearchResult, MemoryEntry

CURRENT_SCHEMA_VERSION = 1


class KnowledgeStore:
    def __init__(self, db_path: Optional[Path] = None):
        cfg = get_config()
        self.db_path = db_path or (cfg.data_dir / "knowledge.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_db(self) -> None:
        """
        Executes idempotent schema migrations and creates FTS5 virtual tables.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Migration tracking table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )

            # Check applied version
            cursor.execute("SELECT MAX(version) FROM schema_migrations;")
            row = cursor.fetchone()
            current_ver = row[0] if (row and row[0] is not None) else 0

            if current_ver < 1:
                # 2. Documents metadata table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        collection TEXT NOT NULL,
                        source_path TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        metadata_json TEXT DEFAULT '{}'
                    );
                    """
                )

                # 3. Document chunks table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        chunk_index INTEGER NOT NULL,
                        chunk_identifier TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        token_estimate INTEGER NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    """
                )

                # 4. FTS5 Virtual Table for full-text keyword retrieval
                cursor.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
                        chunk_identifier UNINDEXED,
                        title,
                        content,
                        tokenize='porter unicode61'
                    );
                    """
                )

                # 5. Durable User Memories table (Preferences & verified project facts)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT NOT NULL UNIQUE,
                        value TEXT NOT NULL,
                        category TEXT NOT NULL DEFAULT 'project_fact',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )

                # 6. Retrieval audit events
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS retrieval_audits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query TEXT NOT NULL,
                        matched_chunks INTEGER NOT NULL,
                        duration_ms REAL NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    """
                )

                cursor.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                    (1, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()

    def upsert_document(
        self,
        collection: str,
        source_path: str,
        title: str,
        content_hash: str,
        size_bytes: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, bool]:
        """
        Inserts or verifies existing document by source_path.
        Returns: (doc_id, was_modified_or_new)
        """
        now = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content_hash FROM documents WHERE source_path = ?;", (source_path,))
            existing = cursor.fetchone()

            if existing:
                doc_id = existing["id"]
                if existing["content_hash"] == content_hash:
                    # Unmodified document, skip re-chunking
                    return doc_id, False

                # Modified: delete old chunks and update document metadata
                cursor.execute("DELETE FROM document_chunks WHERE document_id = ?;", (doc_id,))
                cursor.execute(
                    """
                    UPDATE documents
                    SET title = ?, content_hash = ?, size_bytes = ?, updated_at = ?, metadata_json = ?
                    WHERE id = ?;
                    """,
                    (title, content_hash, size_bytes, now, meta_str, doc_id),
                )
                conn.commit()
                return doc_id, True
            else:
                cursor.execute(
                    """
                    INSERT INTO documents (collection, source_path, title, content_hash, size_bytes, created_at, updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (collection, source_path, title, content_hash, size_bytes, now, now, meta_str),
                )
                doc_id = cursor.lastrowid
                conn.commit()
                return doc_id, True

    def insert_chunk(
        self,
        document_id: int,
        chunk_index: int,
        chunk_identifier: str,
        title: str,
        content: str,
        token_estimate: int,
    ) -> int:
        """
        Inserts a chunk into document_chunks and indexes it in document_chunks_fts.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO document_chunks (document_id, chunk_index, chunk_identifier, title, content, token_estimate, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (document_id, chunk_index, chunk_identifier, title, content, token_estimate, now),
            )
            chunk_id = cursor.lastrowid
            # Index into FTS5
            cursor.execute(
                """
                INSERT INTO document_chunks_fts (chunk_identifier, title, content)
                VALUES (?, ?, ?);
                """,
                (chunk_identifier, title, content),
            )
            conn.commit()
            return chunk_id

    def search_fts(
        self,
        query: str,
        collection: Optional[str] = None,
        limit: int = 3,
    ) -> List[KnowledgeSearchResult]:
        """
        Performs BM25-ranked full-text search against document_chunks_fts.
        """
        t0 = time.perf_counter()
        # Clean query tokens for safe FTS5 MATCH syntax
        tokens = [t.strip("\"'()[]{}*^:?") for t in query.split() if len(t) > 1]
        if not tokens:
            return []

        # Join tokens with OR or AND
        clean_match = " OR ".join(f'"{t}"' for t in tokens)

        results: List[KnowledgeSearchResult] = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if collection:
                sql = """
                    SELECT document_chunks_fts.chunk_identifier, document_chunks_fts.title, 
                           document_chunks_fts.content, d.source_path, d.collection, 
                           bm25(document_chunks_fts) as rank
                    FROM document_chunks_fts
                    JOIN document_chunks c ON c.chunk_identifier = document_chunks_fts.chunk_identifier
                    JOIN documents d ON d.id = c.document_id
                    WHERE document_chunks_fts MATCH ? AND d.collection = ?
                    ORDER BY rank
                    LIMIT ?;
                """
                params = (clean_match, collection, limit)
            else:
                sql = """
                    SELECT document_chunks_fts.chunk_identifier, document_chunks_fts.title, 
                           document_chunks_fts.content, d.source_path, d.collection, 
                           bm25(document_chunks_fts) as rank
                    FROM document_chunks_fts
                    JOIN document_chunks c ON c.chunk_identifier = document_chunks_fts.chunk_identifier
                    JOIN documents d ON d.id = c.document_id
                    WHERE document_chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?;
                """
                params = (clean_match, limit)

            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                for r in rows:
                    results.append(
                        KnowledgeSearchResult(
                            chunk_identifier=r["chunk_identifier"],
                            title=r["title"],
                            source_path=r["source_path"],
                            collection=r["collection"],
                            content=r["content"],
                            score=float(r["rank"]),
                        )
                    )
            except sqlite3.OperationalError:
                # Return empty on syntax error
                return []

            # Record audit event
            duration_ms = (time.perf_counter() - t0) * 1000
            cursor.execute(
                "INSERT INTO retrieval_audits (query, matched_chunks, duration_ms, created_at) VALUES (?, ?, ?, ?);",
                (query, len(results), duration_ms, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

        return results

    # -------------------------------------------------------------
    # Durable User Memory CRUD Operations
    # -------------------------------------------------------------
    def set_memory(self, key: str, value: str, category: str = "project_fact") -> MemoryEntry:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO memories (key, value, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, category = excluded.category, updated_at = excluded.updated_at;
                """,
                (key, value, category, now, now),
            )
            conn.commit()
            return self.get_memory(key)  # type: ignore

    def get_memory(self, key: str) -> Optional[MemoryEntry]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, key, value, category, created_at, updated_at FROM memories WHERE key = ?;", (key,))
            row = cursor.fetchone()
            if not row:
                return None
            return MemoryEntry(
                id=row["id"],
                key=row["key"],
                value=row["value"],
                category=row["category"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_memories(self, category: Optional[str] = None) -> List[MemoryEntry]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "SELECT id, key, value, category, created_at, updated_at FROM memories WHERE category = ? ORDER BY key;",
                    (category,),
                )
            else:
                cursor.execute("SELECT id, key, value, category, created_at, updated_at FROM memories ORDER BY key;")
            rows = cursor.fetchall()
            return [
                MemoryEntry(
                    id=r["id"],
                    key=r["key"],
                    value=r["value"],
                    category=r["category"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def delete_memory(self, key: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE key = ?;", (key,))
            conn.commit()
            return cursor.rowcount > 0

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents;")
            doc_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM document_chunks;")
            chunk_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM memories;")
            mem_count = cursor.fetchone()[0]
            return {
                "documents": doc_count,
                "chunks": chunk_count,
                "memories": mem_count,
                "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            }
