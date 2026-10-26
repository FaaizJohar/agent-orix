"""
Adaptive Task Planner for CIE.
Decomposes user requests into ordered, validated execution steps, generates capability
explanations, and produces strictly typed TaskPlan models.
"""

import uuid
from typing import Any, Dict, List, Optional

from cie.planning.schemas import (
    PlanStatus,
    PlanStep,
    PlanValidationError,
    RetryPolicy,
    StepStatus,
    TaskPlan,
    VerificationRequirement,
    validate_plan_with_registry,
)
from cie.planning.selector import IntelligentSkillSelector
from cie.skills.registry import SkillRegistry, get_default_registry


class AdaptivePlanner:
    """
    Constructs and validates structured TaskPlans from user goals.
    """

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        selector: Optional[IntelligentSkillSelector] = None,
    ):
        self.registry = registry or get_default_registry()
        self.selector = selector or IntelligentSkillSelector(self.registry)

    def create_plan(
        self,
        goal: str,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskPlan:
        """
        Creates a validated TaskPlan from a user prompt or goal.
        """
        task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        metadata = metadata or {}

        # 1. Check for unsupported capabilities first
        unsupported_reason = self.selector.detect_unsupported_capability(goal)
        if unsupported_reason:
            plan = TaskPlan(
                task_id=task_id,
                goal=goal,
                status=PlanStatus.FAILED,
                direct_answer=(
                    f"Requested operation is unsupported: {unsupported_reason}\n\n"
                    "Cavrix executes only approved developer and inspection skills from its verified registry."
                ),
                metadata=metadata,
            )
            return plan

        # 2. Check for purely informational / direct-answer requests
        if self.selector.is_informational_or_direct(goal):
            plan = TaskPlan(
                task_id=task_id,
                goal=goal,
                status=PlanStatus.COMPLETED,
                direct_answer="Direct answer requested; no tool execution required.",
                metadata=metadata,
            )
            return plan

        # 3. Match prompt against registered skills
        matches = self.selector.match_skills_for_prompt(goal)

        # If no skills matched and no direct answer flagged, return direct fallback
        if not matches:
            plan = TaskPlan(
                task_id=task_id,
                goal=goal,
                status=PlanStatus.COMPLETED,
                direct_answer="Direct answer: no registered tools required for this request. Processing via standard synthesis.",
                metadata=metadata,
            )
            return plan

        # 4. Check for missing required parameters in matched skills
        for match in matches:
            if match.missing_parameters:
                plan = TaskPlan(
                    task_id=task_id,
                    goal=goal,
                    status=PlanStatus.BLOCKED,
                    clarification_needed=match.clarification_prompt,
                    selection_explanations=[
                        {"skill_id": match.skill_id, "reason": match.reason}
                    ],
                    metadata=metadata,
                )
                return plan

        # 5. Build ordered steps
        steps: List[PlanStep] = []
        explanations: List[Dict[str, str]] = []

        for idx, match in enumerate(matches[:5], start=1):
            step_id = f"step_{idx}"
            tool_def = self.registry.get_tool(match.skill_id)
            if not tool_def:
                continue

            # Sequential dependency: step N depends on step N-1 if compound
            deps = [f"step_{idx - 1}"] if idx > 1 else []

            # Determine expected verification
            verif = VerificationRequirement(
                expected_type=match.skill_id,
                description=f"Verify {tool_def.display_name} output validity.",
            )

            step = PlanStep(
                step_id=step_id,
                skill_id=match.skill_id,
                arguments=match.extracted_arguments,
                purpose=f"Execute {tool_def.display_name} to fulfill: {match.reason}",
                dependencies=deps,
                expected_outcome=f"Valid structured output from {tool_def.name}.",
                risk=tool_def.risk,
                permission=tool_def.permission,
                requires_approval=tool_def.requires_approval,
                status=StepStatus.AWAITING_APPROVAL if tool_def.requires_approval else StepStatus.PENDING,
                retry_policy=RetryPolicy(max_retries=1, retry_delay_seconds=0.2),
                verification=verif,
            )
            steps.append(step)
            explanations.append({
                "step_id": step_id,
                "skill_id": match.skill_id,
                "reason": match.reason,
            })

        plan = TaskPlan(
            task_id=task_id,
            goal=goal,
            steps=steps,
            status=PlanStatus.PENDING,
            selection_explanations=explanations,
            metadata=metadata,
        )

        # 6. Validate constructed plan against SkillRegistry and DAG rules
        validate_plan_with_registry(plan, self.registry)
        return plan
