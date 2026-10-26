"""
Typed data models and DAG validation rules for CIE Task Planning.
"""

from enum import Enum
import time
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, ValidationError

from cie.skills.schemas import PermissionLevel, RiskLevel
from cie.skills.registry import SkillRegistry


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class PlanStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ErrorCategory(str, Enum):
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class RetryPolicy(BaseModel):
    max_retries: int = Field(default=1, ge=0, le=2, description="Upper bound on retries (max 2)")
    retry_delay_seconds: float = Field(default=0.2, ge=0.0, le=5.0)
    is_retryable: bool = Field(default=True, description="False for mutating actions or fatal errors")


class VerificationRequirement(BaseModel):
    expected_type: str = Field(default="generic", description="Verification strategy type")
    required_keys: List[str] = Field(default_factory=list, description="Keys that must be present in result")
    criteria: Dict[str, Any] = Field(default_factory=dict, description="Expected values or boolean conditions")
    description: Optional[str] = None


class PlanStep(BaseModel):
    step_id: str = Field(..., description="Unique step identifier, e.g. 'step_1'")
    skill_id: str = Field(..., description="Registered tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    purpose: str = Field(..., description="Human-readable explanation of what this step achieves")
    dependencies: List[str] = Field(default_factory=list, description="List of step_ids that must complete prior to this step")
    expected_outcome: str = Field(..., description="Expected state or result format")
    
    # Security attributes strictly derived from SkillRegistry, never trusted from untrusted inputs
    risk: RiskLevel = RiskLevel.LOW
    permission: PermissionLevel = PermissionLevel.READ_ONLY
    requires_approval: bool = False
    approval_token: Optional[str] = None
    
    # Runtime status tracking
    status: StepStatus = StepStatus.PENDING
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    verification: Optional[VerificationRequirement] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    duration_ms: float = 0.0
    retries_attempted: int = 0
    evidence_status: str = "UNKNOWN"
    evidence_record: Optional[Dict[str, Any]] = None


class TaskPlan(BaseModel):
    task_id: str = Field(..., description="Unique plan/task identifier")
    goal: str = Field(..., description="User's original goal or problem description")
    steps: List[PlanStep] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING
    max_steps: int = Field(default=8, ge=1, le=8, description="Hard maximum of 8 steps per plan initially")
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=120.0, description="Wall-clock execution deadline")
    
    # Diagnostic and audit traces
    execution_trace: List[Dict[str, Any]] = Field(default_factory=list)
    selection_explanations: List[Dict[str, str]] = Field(default_factory=list)
    clarification_needed: Optional[str] = None
    direct_answer: Optional[str] = None
    final_summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None


class PlanValidationError(Exception):
    """Raised when a plan fails schema, registry, argument, or DAG validation."""
    pass


def validate_plan_dag(steps: List[PlanStep]) -> List[str]:
    """
    Validates that steps form a Directed Acyclic Graph (DAG) with no cycles.
    Returns a topologically sorted list of step_ids.
    Raises PlanValidationError if cycles or invalid dependencies are detected.
    """
    step_ids: Set[str] = set()
    step_map: Dict[str, PlanStep] = {}

    for s in steps:
        if s.step_id in step_ids:
            raise PlanValidationError(f"Duplicate step_id '{s.step_id}' found in plan.")
        step_ids.add(s.step_id)
        step_map[s.step_id] = s

    # Check that all dependencies point to existing steps
    for s in steps:
        for dep in s.dependencies:
            if dep not in step_ids:
                raise PlanValidationError(
                    f"Step '{s.step_id}' depends on non-existent step '{dep}'."
                )
            if dep == s.step_id:
                raise PlanValidationError(
                    f"Step '{s.step_id}' cannot depend on itself."
                )

    # Topological sort using Kahn's algorithm
    in_degree: Dict[str, int] = {sid: 0 for sid in step_ids}
    adj: Dict[str, List[str]] = {sid: [] for sid in step_ids}

    for s in steps:
        for dep in s.dependencies:
            adj[dep].append(s.step_id)
            in_degree[s.step_id] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    topological_order: List[str] = []

    while queue:
        curr = queue.pop(0)
        topological_order.append(curr)
        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(topological_order) != len(step_ids):
        raise PlanValidationError(
            "Cycle detected in plan dependencies. Plans must be a Directed Acyclic Graph (DAG)."
        )

    return topological_order


def validate_plan_with_registry(plan: TaskPlan, registry: SkillRegistry) -> None:
    """
    Validates plan against the SkillRegistry:
    1. Rejects unknown skills.
    2. Overwrites security attributes (risk, permission, requires_approval) from trusted tool definition.
    3. Enforces zero retries for mutating operations.
    4. Validates arguments against registered input models.
    5. Checks DAG validity and plan step count bounds.
    """
    if len(plan.steps) > plan.max_steps:
        raise PlanValidationError(
            f"Plan exceeds maximum allowable step count ({len(plan.steps)} > {plan.max_steps})."
        )

    if not plan.steps and not plan.direct_answer and not plan.clarification_needed:
        raise PlanValidationError("Plan must contain at least one step or a direct answer.")

    # Validate DAG structure
    validate_plan_dag(plan.steps)

    for step in plan.steps:
        tool_def = registry.get_tool(step.skill_id)
        if not tool_def:
            raise PlanValidationError(
                f"Unknown skill '{step.skill_id}'. This skill is not registered in the Skills Registry."
            )

        if not tool_def.enabled:
            raise PlanValidationError(f"Skill '{step.skill_id}' is currently disabled.")

        # STRICT ENFORCEMENT: Never trust permission or risk ratings from model/user input
        step.permission = tool_def.permission
        step.risk = tool_def.risk
        step.requires_approval = tool_def.requires_approval

        # For mutating actions (LOCAL_WRITE, EXTERNAL_WRITE), never auto-retry
        if tool_def.permission in (PermissionLevel.LOCAL_WRITE, PermissionLevel.EXTERNAL_WRITE):
            step.retry_policy.max_retries = 0
            step.retry_policy.is_retryable = False

        # Validate arguments against Pydantic schema if input_model exists
        if tool_def.input_model:
            try:
                tool_def.input_model.model_validate(step.arguments)
            except ValidationError as e:
                raise PlanValidationError(
                    f"Invalid arguments for skill '{step.skill_id}': {str(e)}"
                )
