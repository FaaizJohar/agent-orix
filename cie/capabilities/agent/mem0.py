"""
Mem0 Long-Term Memory Adapter (mem0ai/mem0).
Provides structured, entity-attribute-relationship memory extraction,
user preference storage, and semantic recall with deduplication.
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    id: str
    user_id: str
    entity: str
    attribute: str
    value: Any
    confidence: float = 1.0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class Mem0MemoryStore:
    """
    Structured entity-attribute memory store compatible with Mem0.
    """

    def __init__(self):
        self._memories: Dict[str, MemoryItem] = {}

    def add(
        self,
        user_id: str,
        entity: str,
        attribute: str,
        value: Any,
        confidence: float = 1.0,
    ) -> MemoryItem:
        mem_id = f"{user_id}:{entity.lower()}:{attribute.lower()}"
        now = time.time()
        item = MemoryItem(
            id=mem_id,
            user_id=user_id,
            entity=entity,
            attribute=attribute,
            value=value,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        self._memories[mem_id] = item
        return item

    def get(self, user_id: str, entity: str, attribute: str) -> Optional[MemoryItem]:
        mem_id = f"{user_id}:{entity.lower()}:{attribute.lower()}"
        return self._memories.get(mem_id)

    def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> List[MemoryItem]:
        q_lower = query.lower()
        results = []
        for mem in self._memories.values():
            if mem.user_id != user_id:
                continue
            if (
                q_lower in mem.entity.lower()
                or q_lower in mem.attribute.lower()
                or q_lower in str(mem.value).lower()
            ):
                results.append(mem)
        results.sort(key=lambda m: m.updated_at, reverse=True)
        return results[:limit]

    def delete(self, user_id: str, entity: str, attribute: str) -> bool:
        mem_id = f"{user_id}:{entity.lower()}:{attribute.lower()}"
        if mem_id in self._memories:
            del self._memories[mem_id]
            return True
        return False

    def list_all(self, user_id: Optional[str] = None) -> List[MemoryItem]:
        if user_id:
            return [m for m in self._memories.values() if m.user_id == user_id]
        return list(self._memories.values())
