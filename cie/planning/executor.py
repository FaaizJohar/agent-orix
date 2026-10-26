"""
Controlled, bounded Plan Execution Engine for CIE.
Coordinates DAG resolution, pre-invocation permission checks, approval gates,
bounded retries, wall-clock deadlines, cancellation, and execution tracing.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from cie.planning.schemas import (
    ErrorCategory,
    PlanStatus,
    PlanStep,
    PlanValidationError,
    StepStatus,
    TaskPlan,
    validate_plan_dag,
    validate_plan_with_registry,
)
from cie.planning.verifier import PlanVerifier
from cie.safety import redact_secrets
from cie.skills.executor import SkillExecutor
from cie.skills.schemas import (
    PermissionLevel,
    ToolExecutionRequest,
    ToolExecutionResult,
)
from cie.truth.verifier import PostconditionVerifier

logger = logging.getLogger("cie.planning.executor")


class BoundedPlanExecutor:
    """
    Executes validated TaskPlans within strict time, step, and security bounds.
    """

    def __init__(
        self,
        skill_executor: Optional[SkillExecutor] = None,
        verifier: Optional[PlanVerifier] = None,
    ):
        self.skill_executor = skill_executor or SkillExecutor()
        self.verifier = verifier or PlanVerifier()
        # Storage for active cancellation requests: task_id -> True
        self._cancellation_flags: Dict[str, bool] = {}

    def cancel_task(self, task_id: str) -> bool:
        """Flags an in-flight task for immediate cancellation."""
        self._cancellation_flags[task_id] = True
        return True

    async def execute_plan(self, plan: TaskPlan) -> TaskPlan:
        """
        Executes a TaskPlan step by step in DAG order.
        """
        start_time = time.perf_counter()

        # If plan is already in a terminal state
        if plan.status in (PlanStatus.COMPLETED, PlanStatus.CANCELLED):
            if not plan.final_summary and plan.direct_answer:
                plan.final_summary = plan.direct_answer
            return plan

        if not plan.steps:
            if plan.direct_answer:
                if plan.status != PlanStatus.FAILED:
                    plan.status = PlanStatus.COMPLETED
                plan.final_summary = plan.direct_answer
            elif plan.clarification_needed:
                plan.status = PlanStatus.BLOCKED
                plan.final_summary = f"Clarification Required: {plan.clarification_needed}"
            return plan

        # Pre-execution validation
        try:
            validate_plan_with_registry(plan, self.skill_executor.registry)
        except PlanValidationError as e:
            plan.status = PlanStatus.FAILED
            plan.final_summary = f"Plan validation failed: {str(e)}"
            plan.execution_trace.append({
                "action": "PlanValidation",
                "status": "FAILED",
                "detail": str(e),
                "timestamp": time.time(),
            })
            return plan

        # Determine topological execution order
        ordered_step_ids = validate_plan_dag(plan.steps)
        step_map: Dict[str, PlanStep] = {s.step_id: s.model_copy() for s in plan.steps}

        plan.status = PlanStatus.IN_PROGRESS
        successful_steps = 0
        failed_steps = 0
        blocked_approval = False

        for step_id in ordered_step_ids:
            step = step_map[step_id]

            # 1. Check task cancellation
            if self._cancellation_flags.get(plan.task_id, False):
                step.status = StepStatus.SKIPPED
                step.error = "Plan execution cancelled by user."
                plan.status = PlanStatus.CANCELLED
                plan.execution_trace.append({
                    "step_id": step.step_id,
                    "action": "ExecutionCancelled",
                    "status": "CANCELLED",
                    "timestamp": time.time(),
                })
                break

            # 2. Check wall-clock plan timeout
            elapsed = time.perf_counter() - start_time
            if elapsed > plan.timeout_seconds:
                step.status = StepStatus.SKIPPED
                step.error = f"Plan exceeded wall-clock timeout of {plan.timeout_seconds:.1f}s."
                plan.status = PlanStatus.FAILED
                plan.execution_trace.append({
                    "step_id": step.step_id,
                    "action": "ExecutionTimeout",
                    "status": "TIMEOUT",
                    "detail": f"Elapsed {elapsed:.2f}s exceeded deadline {plan.timeout_seconds:.1f}s.",
                    "timestamp": time.time(),
                })
                break

            # 3. Check dependencies
            prereq_failed = False
            for dep_id in step.dependencies:
                dep_step = step_map.get(dep_id)
                if not dep_step or dep_step.status != StepStatus.SUCCEEDED:
                    prereq_failed = True
                    step.status = StepStatus.SKIPPED
                    step.error = f"Prerequisite step '{dep_id}' did not succeed (status: {dep_step.status if dep_step else 'MISSING'})."
                    plan.execution_trace.append({
                        "step_id": step.step_id,
                        "action": "PrerequisiteCheck",
                        "status": "SKIPPED",
                        "detail": step.error,
                        "timestamp": time.time(),
                    })
                    break

            if prereq_failed:
                continue

            # 4. Check approval requirement
            tool_def = self.skill_executor.registry.get_tool(step.skill_id)
            if tool_def and tool_def.requires_approval and not step.approval_token:
                step.status = StepStatus.AWAITING_APPROVAL
                plan.status = PlanStatus.BLOCKED
                blocked_approval = True
                plan.execution_trace.append({
                    "step_id": step.step_id,
                    "action": "ApprovalGate",
                    "status": "BLOCKED",
                    "detail": f"Tool '{step.skill_id}' requires explicit user approval token.",
                    "timestamp": time.time(),
                })
                # Pause plan execution at approval gate
                break

            # 5. Execute step with bounded retries
            step.status = StepStatus.RUNNING
            retries = 0
            max_retries = step.retry_policy.max_retries if step.retry_policy.is_retryable else 0

            while retries <= max_retries:
                step_start = time.perf_counter()
                tool_req = ToolExecutionRequest(
                    tool_name=step.skill_id,
                    arguments=step.arguments,
                    approved_by_user=bool(step.approval_token),
                    approval_token=step.approval_token,
                    session_id=plan.task_id,
                )

                exec_result = await self.skill_executor.execute(tool_req)
                step.duration_ms = (time.perf_counter() - step_start) * 1000

                # Outcome verification
                verified, verif_error = self.verifier.verify_step_outcome(step, exec_result)
                post_record = PostconditionVerifier.verify_operation(
                    task_id=plan.task_id,
                    operation=step.purpose,
                    tool_name=step.skill_id,
                    arguments=step.arguments,
                    raw_result=exec_result,
                    expected_postcondition=step.expected_outcome,
                )
                step.evidence_status = post_record.uncertainty.value
                step.evidence_record = post_record.model_dump()

                if not post_record.is_postcondition_verified and verified:
                    verified = False
                    verif_error = post_record.failure_reason or "Postcondition verification check failed."

                if verified:
                    step.status = StepStatus.SUCCEEDED
                    step.result = exec_result.result
                    step.error = None
                    successful_steps += 1
                    plan.execution_trace.append({
                        "step_id": step.step_id,
                        "action": f"Execute:{step.skill_id}",
                        "status": "SUCCEEDED",
                        "duration_ms": round(step.duration_ms, 2),
                        "timestamp": time.time(),
                    })
                    break
                else:
                    err_msg = verif_error or exec_result.error or "Verification check failed."
                    err_cat = self.verifier.classify_error(err_msg)
                    step.error = err_msg
                    step.error_category = err_cat

                    plan.execution_trace.append({
                        "step_id": step.step_id,
                        "action": f"Execute:{step.skill_id}",
                        "status": "ATTEMPT_FAILED",
                        "error_category": err_cat.value,
                        "detail": redact_secrets(err_msg),
                        "retries_attempted": retries,
                        "timestamp": time.time(),
                    })

                    # Critical security violation: abort plan immediately
                    if err_cat == ErrorCategory.SECURITY_VIOLATION:
                        step.status = StepStatus.FAILED
                        plan.status = PlanStatus.FAILED
                        failed_steps += 1
                        # Break out of both retry loop and step execution
                        break

                    # Check if action was consequential
                    is_consequential = (
                        (tool_def and tool_def.requires_approval)
                        or (tool_def and tool_def.permission in (PermissionLevel.LOCAL_WRITE, PermissionLevel.EXTERNAL_WRITE))
                        or bool(step.arguments.get("consequential", False))
                    )

                    # Stage 2 constraint: Never auto-retry a consequential action when its outcome is uncertain. Stop and ask the user.
                    if is_consequential:
                        step.status = StepStatus.AWAITING_APPROVAL
                        plan.status = PlanStatus.BLOCKED
                        step.error = f"Uncertain outcome on consequential action '{step.skill_id}': {err_msg}. Auto-retry prohibited; user guidance required."
                        plan.execution_trace.append({
                            "step_id": step.step_id,
                            "action": f"UncertainOutcome:{step.skill_id}",
                            "status": "BLOCKED",
                            "detail": step.error,
                            "timestamp": time.time(),
                        })
                        blocked_approval = True
                        break

                    # Non-retryable errors
                    if err_cat in (ErrorCategory.VALIDATION_ERROR, ErrorCategory.PERMISSION_DENIED, ErrorCategory.NOT_FOUND):
                        step.status = StepStatus.FAILED
                        failed_steps += 1
                        break

                    # Check if retry permitted
                    if retries < max_retries and step.retry_policy.is_retryable:
                        retries += 1
                        step.retries_attempted = retries
                        await asyncio.sleep(step.retry_policy.retry_delay_seconds)
                    else:
                        step.status = StepStatus.FAILED
                        failed_steps += 1
                        break

            # If security violation stopped execution, abort overall loop
            if step.error_category == ErrorCategory.SECURITY_VIOLATION:
                break

        # Re-attach updated steps in ordered sequence
        plan.steps = [step_map[sid] for sid in ordered_step_ids]
        plan.completed_at = time.time()

        # Resolve overall plan status
        if blocked_approval:
            plan.status = PlanStatus.BLOCKED
        elif plan.status not in (PlanStatus.CANCELLED, PlanStatus.FAILED):
            if successful_steps == len(plan.steps):
                plan.status = PlanStatus.COMPLETED
            elif successful_steps > 0:
                plan.status = PlanStatus.PARTIALLY_COMPLETED
            else:
                plan.status = PlanStatus.FAILED

        # Synthesize final summary
        plan.final_summary = self._generate_final_summary(plan)
        return plan

    def _generate_final_summary(self, plan: TaskPlan) -> str:
        """Synthesizes a clean, human-readable execution report."""
        if plan.status == PlanStatus.COMPLETED and plan.direct_answer:
            return plan.direct_answer

        lines = [
            f"### Task Plan Report: `{plan.task_id}`",
            f"**Goal:** {plan.goal}",
            f"**Status:** `{plan.status.value}`\n",
        ]

        if plan.clarification_needed:
            lines.append(f"**Clarification Required:** {plan.clarification_needed}\n")

        lines.append("#### Execution Steps Summary:")
        for step in plan.steps:
            status_emoji = {
                StepStatus.SUCCEEDED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
                StepStatus.AWAITING_APPROVAL: "⏸️ (Awaiting Approval)",
                StepStatus.RUNNING: "🔄",
                StepStatus.PENDING: "⏳",
            }.get(step.status, "❓")

            lines.append(f"- **{step.step_id}** (`{step.skill_id}`): {status_emoji} {step.status.value}")
            lines.append(f"  *Purpose:* {step.purpose}")
            if step.status == StepStatus.SUCCEEDED:
                lines.append(f"  *Outcome:* Verified ({step.duration_ms:.2f}ms)")
            elif step.status == StepStatus.FAILED:
                lines.append(f"  *Error [{step.error_category.value if step.error_category else 'UNKNOWN'}]:* {step.error}")
            elif step.status == StepStatus.SKIPPED:
                lines.append(f"  *Reason:* {step.error}")

        return redact_secrets("\n".join(lines))
