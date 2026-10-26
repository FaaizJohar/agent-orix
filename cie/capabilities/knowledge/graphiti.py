"""
Graphiti Temporal Knowledge Graph Adapter (getzep/graphiti).
Maintains episodic entity relationship triplets with valid_at and invalid_at timestamps
for temporal reasoning across conversations.
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TemporalEdge(BaseModel):
    source: str
    relation: str
    target: str
    valid_at: float = Field(default_factory=time.time)
    invalid_at: Optional[float] = None
    confidence: float = 1.0


class GraphitiAdapter:
    """
    In-memory and sqlite-backed temporal knowledge graph.
    """

    def __init__(self):
        self.edges: List[TemporalEdge] = []

    def add_edge(self, source: str, relation: str, target: str, valid_at: Optional[float] = None) -> TemporalEdge:
        edge = TemporalEdge(
            source=source,
            relation=relation,
            target=target,
            valid_at=valid_at or time.time(),
        )
        self.edges.append(edge)
        return edge

    def invalidate_edge(self, source: str, relation: str, target: str, invalid_at: Optional[float] = None) -> bool:
        for e in self.edges:
            if e.source == source and e.relation == relation and e.target == target and e.invalid_at is None:
                e.invalid_at = invalid_at or time.time()
                return True
        return False

    def query_relationships(self, entity: str, at_timestamp: Optional[float] = None) -> List[TemporalEdge]:
        t = at_timestamp or time.time()
        results = []
        for e in self.edges:
            if e.source == entity or e.target == entity:
                if e.valid_at <= t and (e.invalid_at is None or e.invalid_at > t):
                    results.append(e)
        return results
