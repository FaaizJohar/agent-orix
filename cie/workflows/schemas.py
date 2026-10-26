"""
Schemas and State Models for Multi-Step Real-World Workflows in CavrixCode.
"""

from enum import Enum
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowType(str, Enum):
    DOCUMENT_INTELLIGENCE = "DOCUMENT_INTELLIGENCE"
    CODEBASE_REPAIR = "CODEBASE_REPAIR"
    RESEARCH_VERIFICATION = "RESEARCH_VERIFICATION"


class WorkflowState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ─── Inputs for the 3 Workflows ──────────────────────────────────────────────

class DocumentIntelligenceInput(BaseModel):
    file_path: Optional[str] = Field(None, description="Path to document file (.md, .txt, .pdf, .docx, .html, .csv)")
    web_url: Optional[str] = Field(None, description="Web URL to process with Crawl4AI")
    raw_content: Optional[str] = Field(None, description="Raw text or html content")
    enable_ocr: bool = Field(False, description="Whether OCR is requested (checked against availability)")
    max_file_size_mb: float = Field(25.0, description="Max allowed file size in MB")
    summary_instructions: Optional[str] = Field(None, description="Specific summarization instructions")


class CodebaseRepairInput(BaseModel):
    workspace_root: str = Field(..., description="Root directory of target codebase")
    target_file: str = Field(..., description="Path to file to inspect and repair")
    error_or_test_command: Optional[str] = Field(None, description="Test command or error description to reproduce")
    proposed_patch: Optional[str] = Field(None, description="Pre-computed diff or replacement code")
    approval_token: Optional[str] = Field(None, description="HMAC approval token for consequential write/execution")
    test_suite_command: Optional[List[str]] = Field(None, description="Command to verify fix in workspace")


class ResearchVerificationInput(BaseModel):
    research_question: str = Field(..., description="The query or hypothesis to research")
    max_sources: int = Field(5, ge=1, le=10, description="Max candidate sources to retrieve")
    cross_verify: bool = Field(True, description="Whether to compare sources for contradictions")
    allow_web_fetch: bool = Field(True, description="Whether live HTTP fetching is permitted")


# ─── Step Trace & Verification ───────────────────────────────────────────────

class WorkflowStep(BaseModel):
    step_index: int
    step_name: str
    status: str = "PENDING"
    duration_ms: float = 0.0
    tool_invoked: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class WorkflowRequest(BaseModel):
    workflow_id: str = Field(..., description="Unique workflow execution ID")
    workflow_type: WorkflowType
    document_input: Optional[DocumentIntelligenceInput] = None
    codebase_input: Optional[CodebaseRepairInput] = None
    research_input: Optional[ResearchVerificationInput] = None
    timeout_seconds: float = Field(60.0, ge=5.0, le=300.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    workflow_id: str
    workflow_type: WorkflowType
    state: WorkflowState
    success: bool
    summary: str
    steps: List[WorkflowStep] = Field(default_factory=list)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    waiting_for_action: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    resumable_checkpoint: Optional[Dict[str, Any]] = None
