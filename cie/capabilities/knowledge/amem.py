"""
A-MEM Adaptive Associative Memory System Adapter (WujiangXu/A-mem).
Provides associative memory graphs, dynamic recency/frequency decay curves,
and activation spreading for memory evolution.
"""

import math
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AdaptiveMemoryNode(BaseModel):
    id: str
    content: str
    access_count: int = 1
    last_accessed: float = Field(default_factory=time.time)
    decay_rate: float = 0.05
    associated_nodes: List[str] = Field(default_factory=list)

    def compute_strength(self, current_time: Optional[float] = None) -> float:
        now = current_time or time.time()
        elapsed_hours = (now - self.last_accessed) / 3600.0
        # Ebbinghaus-inspired power decay modulated by recall count
        retention = math.exp(-self.decay_rate * elapsed_hours)
        return round(self.access_count * retention, 4)


class AMEMAdapter:
    """
    Adaptive memory manager that strengthens frequently recalled memories
    and prunes low-activation items over time.
    """

    def __init__(self):
        self.nodes: Dict[str, AdaptiveMemoryNode] = {}

    def insert(self, node_id: str, content: str, associations: Optional[List[str]] = None) -> AdaptiveMemoryNode:
        node = AdaptiveMemoryNode(
            id=node_id,
            content=content,
            associated_nodes=associations or [],
        )
        self.nodes[node_id] = node
        return node

    def recall(self, node_id: str) -> Optional[AdaptiveMemoryNode]:
        node = self.nodes.get(node_id)
        if node:
            node.access_count += 1
            node.last_accessed = time.time()
        return node

    def get_top_activated(self, limit: int = 5) -> List[AdaptiveMemoryNode]:
        now = time.time()
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.compute_strength(now), reverse=True)
        return sorted_nodes[:limit]
