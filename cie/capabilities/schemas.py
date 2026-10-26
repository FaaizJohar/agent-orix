"""
Capability framework schemas for CavrixCode Phase 12.
Defines metadata, status, and execution contracts for all 30 integrated capabilities.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CapabilityCategory(str, Enum):
    AGENT = "agent_intelligence_execution"
    BROWSER = "browser_research_web"
    KNOWLEDGE = "knowledge_memory_retrieval"
    DOCUMENTS_EVAL = "documents_optimization_eval"
    VISION_EVENTS = "vision_external_events"


class IntegrationType(str, Enum):
    NATIVE = "native_implementation"
    ADAPTER = "compatible_adapter"
    OPTIONAL_SERVICE = "optional_service"
    HYBRID = "hybrid_library"


class CapabilityStatus(str, Enum):
    # Phase 15 explicit statuses
    INTEGRATED_AND_E2E_VERIFIED = "INTEGRATED_AND_E2E_VERIFIED"
    UPSTREAM_LIBRARY_INTEGRATED = "UPSTREAM_LIBRARY_INTEGRATED"
    REMOTE_SERVICE_CLIENT_IMPLEMENTED = "REMOTE_SERVICE_CLIENT_IMPLEMENTED"
    PROTOCOL_ADAPTER_ONLY = "PROTOCOL_ADAPTER_ONLY"
    CUSTOM_REIMPLEMENTATION = "CUSTOM_REIMPLEMENTATION"
    BLOCKED = "BLOCKED"
    NOT_INTEGRATED = "NOT_INTEGRATED"
    
    # Backwards compatibility
    IMPLEMENTED_AND_VERIFIED = "IMPLEMENTED AND VERIFIED"
    PARTIALLY_IMPLEMENTED = "PARTIALLY IMPLEMENTED"
    NOT_STARTED = "NOT STARTED"


class CapabilityMetadata(BaseModel):
    id: int = Field(..., description="Unique capability ID from 1 to 30")
    name: str = Field(..., description="Project / capability name")
    category: CapabilityCategory
    canonical_repo: str = Field(..., description="Official repository URL")
    license: str = Field(..., description="Open source license identifier")
    integration_type: IntegrationType
    status: CapabilityStatus
    enabled: bool = True
    description: str
    tools_provided: List[str] = Field(default_factory=list)
    resource_profile: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
