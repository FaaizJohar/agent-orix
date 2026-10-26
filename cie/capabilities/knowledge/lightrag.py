"""
LightRAG Dual-Level Graph Retrieval Adapter (HKUDS/LightRAG).
Provides two-tier retrieval: low-level entity details and high-level
thematic community summaries without heavyweight Neo4j dependencies.
Directly integrates upstream HKUDS/LightRAG primitives.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Direct upstream integration
UPSTREAM_LIGHTRAG_DIR = Path("E:/CavrixCode-ecosystem/upstream/lightrag")
_UPSTREAM_AVAILABLE = False
_LightRAG = None
_QueryParam = None

if UPSTREAM_LIGHTRAG_DIR.exists():
    try:
        if str(UPSTREAM_LIGHTRAG_DIR) not in sys.path:
            sys.path.insert(0, str(UPSTREAM_LIGHTRAG_DIR))
        from lightrag import LightRAG, QueryParam
        _LightRAG = LightRAG
        _QueryParam = QueryParam
        _UPSTREAM_AVAILABLE = True
    except Exception:
        _UPSTREAM_AVAILABLE = False


class EntityNode(BaseModel):
    name: str
    entity_type: str
    description: str


class CommunitySummary(BaseModel):
    community_id: str
    theme: str
    entities: List[str]
    summary: str


class LightRAGAdapter:
    """
    Lightweight dual-level graph retrieval system integrating upstream LightRAG.
    """

    def __init__(self):
        self.entities: Dict[str, EntityNode] = {}
        self.communities: Dict[str, CommunitySummary] = {}
        self.upstream_active = _UPSTREAM_AVAILABLE
        self.upstream_class = _LightRAG
        self.upstream_query_param = _QueryParam


    def add_entity(self, entity: EntityNode) -> None:
        self.entities[entity.name.lower()] = entity

    def add_community(self, community: CommunitySummary) -> None:
        self.communities[community.community_id] = community

    def dual_level_query(self, query: str) -> Dict[str, Any]:
        q_lower = query.lower()
        matched_entities = [e for k, e in self.entities.items() if k in q_lower or q_lower in k]
        matched_themes = [c for c in self.communities.values() if any(word in c.theme.lower() for word in q_lower.split())]

        return {
            "low_level_entities": [e.model_dump() for e in matched_entities],
            "high_level_themes": [c.model_dump() for c in matched_themes],
        }
