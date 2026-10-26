"""
OpenViking Virtual Filesystem Context Database Adapter (volcengine/OpenViking).
Implements a virtual filesystem hierarchy (viking:// URIs) with L0 (abstract),
L1 (overview), and L2 (full detail) tiered context delivery.
Directly integrates upstream volcengine/OpenViking client.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Direct upstream integration
UPSTREAM_OPENVIKING_DIR = Path("E:/CavrixCode-ecosystem/upstream/openviking")
_UPSTREAM_AVAILABLE = False
_SyncHTTPClient = None

if UPSTREAM_OPENVIKING_DIR.exists():
    try:
        if str(UPSTREAM_OPENVIKING_DIR) not in sys.path:
            sys.path.insert(0, str(UPSTREAM_OPENVIKING_DIR))
        from openviking import SyncHTTPClient
        _SyncHTTPClient = SyncHTTPClient
        _UPSTREAM_AVAILABLE = True
    except Exception:
        _UPSTREAM_AVAILABLE = False


class VikingResourceNode(BaseModel):
    uri: str = Field(..., description="Virtual URI, e.g. 'viking://resources/auth_module'")
    title: str
    l0_abstract: str = Field(..., description="Single-sentence summary for rapid relevance check")
    l1_overview: str = Field(..., description="Core information and usage scenarios")
    l2_detail: str = Field(..., description="Full unabridged content or source code")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OpenVikingAdapter:
    """
    Virtual filesystem context engine replacing blind vector search
    with navigable directory trees and multi-tier token delivery.
    Integrates upstream OpenViking client.
    """

    def __init__(self, endpoint: Optional[str] = None):
        self._nodes: Dict[str, VikingResourceNode] = {}
        self.endpoint = endpoint
        self.upstream_active = _UPSTREAM_AVAILABLE
        self.client = _SyncHTTPClient(endpoint=endpoint) if (_SyncHTTPClient and endpoint) else None


    def add_resource(self, node: VikingResourceNode) -> None:
        self._nodes[node.uri.lower()] = node

    def get_resource(self, uri: str, tier: str = "L1") -> Optional[str]:
        node = self._nodes.get(uri.lower())
        if not node:
            return None
        tier = tier.upper().strip()
        if tier == "L0":
            return node.l0_abstract
        elif tier == "L1":
            return node.l1_overview
        elif tier == "L2":
            return node.l2_detail
        return node.l1_overview

    def list_subtree(self, prefix: str = "viking://") -> List[VikingResourceNode]:
        p = prefix.lower()
        return [n for k, n in self._nodes.items() if k.startswith(p)]
