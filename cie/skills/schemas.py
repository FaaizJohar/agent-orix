"""
Data models and typed schemas for CIE Skills Registry and Execution Engine.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field


class PermissionLevel(str, Enum):
    READ_ONLY = "READ_ONLY"          # Inspect approved public or local resources
    LOCAL_WRITE = "LOCAL_WRITE"      # Modify only explicitly approved local files
    NETWORK_READ = "NETWORK_READ"    # Make approved outbound network requests
    EXTERNAL_WRITE = "EXTERNAL_WRITE"# Perform remote changes (e.g. GitHub mutations)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ToolDefinition(BaseModel):
    name: str = Field(..., description="Unique tool identifier, e.g. 'python_ast_validate'")
    display_name: str
    description: str
    permission: PermissionLevel
    risk: RiskLevel = RiskLevel.LOW
    timeout_seconds: float = 10.0
    rate_limit_per_minute: int = 60
    requires_approval: bool = False
    auth_required: bool = False
    version: str = "1.0.0"
    enabled: bool = True
    model_config = {"arbitrary_types_allowed": True}

    # Optional Pydantic model classes for strict validation
    input_model: Optional[Type[BaseModel]] = None
    output_model: Optional[Type[BaseModel]] = None

    # Reference to Pydantic models for serialization / introspection
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)


from cie.security_tokens import compute_action_token, verify_action_token, mask_token


class ToolExecutionRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    approved_by_user: bool = False
    approval_token: Optional[str] = Field(default=None, description="Cryptographic action-bound approval token")
    session_id: Optional[str] = None


class ToolExecutionResult(BaseModel):
    success: bool
    tool_name: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    permission_used: PermissionLevel
