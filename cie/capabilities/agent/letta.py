"""
Letta Tiered Memory Architecture Adapter (letta-ai/letta, formerly MemGPT).
Implements Core Memory (Persona & Human blocks), Archival Memory,
and Recall Memory with explicit memory modification operations.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CoreMemory(BaseModel):
    persona: str = Field(..., description="Agent personality, principles, and rules")
    human: str = Field(..., description="Facts and details about the user")


class ArchivalPassage(BaseModel):
    id: Optional[int] = None
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float


class LettaMemoryManager:
    """
    Tiered memory manager implementing the Letta/MemGPT architecture.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
        self.core = CoreMemory(
            persona="CavrixCode: Truthful, evidence-driven AI assistant with verifiable execution.",
            human="User: Developer working with local CavrixCode desktop environment.",
        )

    def _init_db(self):
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archival_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recall_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    # Core Memory Operations
    def core_memory_append(self, section: str, text: str) -> bool:
        section = section.lower().strip()
        if section == "persona":
            self.core.persona += "\n" + text.strip()
            return True
        elif section == "human":
            self.core.human += "\n" + text.strip()
            return True
        return False

    def core_memory_replace(self, section: str, old_text: str, new_text: str) -> bool:
        section = section.lower().strip()
        if section == "persona" and old_text in self.core.persona:
            self.core.persona = self.core.persona.replace(old_text, new_text)
            return True
        elif section == "human" and old_text in self.core.human:
            self.core.human = self.core.human.replace(old_text, new_text)
            return True
        return False

    # Archival Memory Operations
    def archival_memory_insert(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        meta_json = json.dumps(metadata or {})
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO archival_memory (content, metadata) VALUES (?, ?)",
                (content, meta_json),
            )
            return cur.lastrowid

    def archival_memory_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            "SELECT id, content, metadata FROM archival_memory WHERE content LIKE ? LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"] or "{}"),
            }
            for r in rows
        ]

    # Recall Memory
    def recall_memory_log(self, role: str, message: str) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO recall_memory (role, message) VALUES (?, ?)",
                (role, message),
            )
            return cur.lastrowid
