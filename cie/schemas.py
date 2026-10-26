"""
Data schemas and type definitions for Cavrix Intelligence Engine (CIE).
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    DIRECT = "DIRECT"
    RESEARCH = "RESEARCH"
    KNOWLEDGE = "KNOWLEDGE"
    SKILL = "SKILL"
    CODE_EXECUTION = "CODE_EXECUTION"
    MULTILINGUAL = "MULTILINGUAL"
    GENERAL = "GENERAL"


class RouteDecision(BaseModel):
    category: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    matched_patterns: List[str] = Field(default_factory=list)
    fallback_applied: bool = False


class CIERequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=65536)
    session_id: Optional[str] = None
    stream: bool = False
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    system_override: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StepRecord(BaseModel):
    step_number: int
    action: str
    status: str
    detail: Optional[str] = None
    duration_ms: float = 0.0


class ExecutionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class CIEResponse(BaseModel):
    status: ExecutionStatus
    content: str
    route: RouteDecision
    steps_taken: List[StepRecord] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthStatus(BaseModel):
    status: str
    version: str
    ollama_endpoint: str
    ollama_connected: bool
    model_name: str
    model_available: bool
    offline_mode: bool
    process_ram_mb: float
    total_visible_ram_mb: float
    uptime_seconds: float
