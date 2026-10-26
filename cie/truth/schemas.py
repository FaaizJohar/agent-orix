"""
CavrixCode Phase 5.1 — Truth, Anti-Sycophancy, and Evidence Data Models.
Defines explicit verification statuses, calibrated uncertainty categories,
lifecycle states, and structured evidence records.
"""

from enum import Enum
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvidenceStatus(str, Enum):
    """
    Calibrated uncertainty levels reflecting actual inspected evidence,
    never subjective or stylistic confidence.
    """
    VERIFIED = "VERIFIED"                  # Directly supported by inspected evidence or reproducible execution
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED" # Multiple consistent pieces of evidence, but direct check incomplete
    INFERRED = "INFERRED"                  # Reasoned conclusion from incomplete evidence
    ESTIMATED = "ESTIMATED"                # Approximate value with stated assumptions
    UNKNOWN = "UNKNOWN"                    # Insufficient evidence to reach a reliable conclusion
    DISPUTED = "DISPUTED"                  # Credible evidence conflicts


class TaskLifecycleStatus(str, Enum):
    """
    Explicit lifecycle states for tasks and operations.
    """
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    UNVERIFIED = "UNVERIFIED"


class EvidenceRecord(BaseModel):
    """
    Structured record maintaining the audit trail for every material operation.
    """
    task_id: str
    requested_operation: str
    intended_target: Optional[str] = None
    tool: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    permission: str = "READ_ONLY"
    approval_status: str = "NOT_REQUIRED"  # NOT_REQUIRED, PENDING, APPROVED, REJECTED
    start_status: TaskLifecycleStatus = TaskLifecycleStatus.NOT_STARTED
    completion_status: TaskLifecycleStatus = TaskLifecycleStatus.NOT_STARTED
    tool_output_summary: Optional[str] = None
    verification_method: str = "semantic_check"
    expected_postcondition: Optional[str] = None
    observed_postcondition: Optional[str] = None
    is_postcondition_verified: bool = False
    failure_reason: Optional[str] = None
    uncertainty: EvidenceStatus = EvidenceStatus.UNKNOWN
    timestamp: float = Field(default_factory=time.time)


class ClaimEvaluation(BaseModel):
    """
    Evaluation of a substantive factual, technical, or self-report claim.
    """
    claim_text: str
    is_supported: bool
    evidence_status: EvidenceStatus
    decisive_evidence: Optional[str] = None
    contradiction_detected: bool = False
    contradiction_detail: Optional[str] = None
    pushback_required: bool = False
    pushback_message: Optional[str] = None
    confidence_calibrated: str = "EVIDENCE_BOUND"
