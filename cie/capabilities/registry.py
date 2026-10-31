"""
Central Capability Registry for CavrixCode.
Tracks, manages, and validates all 30 open-source capabilities.
Auto-populates from E:\CavrixCode-ecosystem\register.json or bundled fallback for complete system parity.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from cie.capabilities.schemas import (
    CapabilityCategory,
    CapabilityMetadata,
    CapabilityStatus,
    IntegrationType,
)


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: Dict[int, CapabilityMetadata] = {}

    def register(self, metadata: CapabilityMetadata) -> None:
        self._capabilities[metadata.id] = metadata

    def get(self, capability_id: int) -> Optional[CapabilityMetadata]:
        return self._capabilities.get(capability_id)

    def get_by_name(self, name: str) -> Optional[CapabilityMetadata]:
        name_lower = name.lower()
        for cap in self._capabilities.values():
            if cap.name.lower() == name_lower:
                return cap
        return None

    def list_all(self) -> List[CapabilityMetadata]:
        return sorted(list(self._capabilities.values()), key=lambda c: c.id)

    def list_by_category(self, category: CapabilityCategory) -> List[CapabilityMetadata]:
        return [c for c in self.list_all() if c.category == category]

    def set_enabled(self, capability_id: int, enabled: bool) -> bool:
        cap = self.get(capability_id)
        if not cap:
            return False
        cap.enabled = enabled
        return True

    def get_status_summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for cap in self._capabilities.values():
            val = cap.status.value
            counts[val] = counts.get(val, 0) + 1
        return counts


_GLOBAL_CAPABILITY_REGISTRY: Optional[CapabilityRegistry] = None


def populate_from_register_json(registry: CapabilityRegistry, register_path: str = "E:/CavrixCode-ecosystem/register.json") -> None:
    p = Path(register_path)
    if not p.exists():
        p = Path(__file__).parent / "data" / "register.json"
    if not p.exists():
        return

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        category_map = {
            "agent_intelligence_execution": CapabilityCategory.AGENT,
            "browser_research_web": CapabilityCategory.BROWSER,
            "knowledge_memory_retrieval": CapabilityCategory.KNOWLEDGE,
            "documents_optimization_eval": CapabilityCategory.DOCUMENTS_EVAL,
            "vision_external_events": CapabilityCategory.VISION_EVENTS,
        }

        for item in data.get("repositories", []):
            cid = item["id"]
            cat_str = item.get("category", "agent_intelligence_execution")
            category = category_map.get(cat_str, CapabilityCategory.AGENT)

            status_str = item.get("phase15_status", item.get("status", "CUSTOM_REIMPLEMENTATION"))
            try:
                status = CapabilityStatus(status_str)
            except ValueError:
                status = CapabilityStatus.CUSTOM_REIMPLEMENTATION

            metadata = CapabilityMetadata(
                id=cid,
                name=item["name"],
                category=category,
                canonical_repo=item.get("canonical_url", ""),
                license=item.get("license", "Unknown"),
                integration_type=IntegrationType.ADAPTER,
                status=status,
                enabled=True,
                description=item.get("reality_notes", f"Ecosystem capability #{cid}: {item['name']}"),
                tools_provided=item.get("tools_provided", []),
                resource_profile=item.get("resource_metrics", {}),
                limitations=item.get("limitations", []),
            )
            registry.register(metadata)
    except Exception as e:
        print(f"Warning: Failed to populate capability registry from {register_path}: {e}")


def get_capability_registry() -> CapabilityRegistry:
    global _GLOBAL_CAPABILITY_REGISTRY
    if _GLOBAL_CAPABILITY_REGISTRY is None:
        _GLOBAL_CAPABILITY_REGISTRY = CapabilityRegistry()
        populate_from_register_json(_GLOBAL_CAPABILITY_REGISTRY)
    return _GLOBAL_CAPABILITY_REGISTRY
