"""
Secure, bounded execution engine for CIE Skills.
Handles parameter validation, permission checks, timeouts, rate limiting, and output redaction.
"""

import asyncio
import inspect
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from pydantic import ValidationError

from cie.safety import redact_secrets
from cie.security_tokens import mask_token, verify_action_token
from cie.skills.registry import SkillRegistry, get_default_registry
from cie.skills.schemas import (
    PermissionLevel,
    RiskLevel,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionResult,
    compute_action_token,
)

logger = logging.getLogger("cie.skills.executor")


class SkillExecutionError(Exception):
    pass


class PermissionDeniedError(SkillExecutionError):
    pass


class RateLimitExceededError(SkillExecutionError):
    pass


class ToolTimeoutError(SkillExecutionError):
    pass


class SkillExecutor:
    """
    Central execution broker for registered skills.
    Ensures safe, permissioned execution with timeouts and audit logging.
    """

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or get_default_registry()
        # Sliding-window rate limit storage: tool_name -> list of unix timestamps
        self._rate_limit_timestamps: Dict[str, List[float]] = {}
        # Single-use consumed approval tokens storage for replay defense
        self._consumed_tokens: Set[str] = set()
        # Audit log entries
        self.audit_log: List[Dict[str, Any]] = []
        # Concurrency safety re-entrant lock
        self._lock = threading.RLock()

    def create_approval_token(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Generates a cryptographically bound action token for approval."""
        return compute_action_token(tool_name, arguments)

    def _check_rate_limit(self, tool_name: str, limit_per_minute: int) -> bool:
        """
        Check if tool invocation is within rate limits for a 60-second sliding window.
        Thread-safe under high concurrent load.
        """
        now = time.time()
        window_start = now - 60.0

        with self._lock:
            if tool_name not in self._rate_limit_timestamps:
                self._rate_limit_timestamps[tool_name] = []

            # Filter out timestamps older than 60s
            self._rate_limit_timestamps[tool_name] = [
                ts for ts in self._rate_limit_timestamps[tool_name] if ts >= window_start
            ]

            if len(self._rate_limit_timestamps[tool_name]) >= limit_per_minute:
                return False

            self._rate_limit_timestamps[tool_name].append(now)
            return True

    def _sanitize_data(self, val: Any) -> Any:
        """Recursively redact secrets in dict/list/str data structures."""
        if isinstance(val, str):
            return redact_secrets(val)
        elif isinstance(val, dict):
            return {k: self._sanitize_data(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self._sanitize_data(v) for v in val]
        return val

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """
        Execute a tool safely according to its specification.
        """
        start_time = time.perf_counter()
        tool_name = request.tool_name

        tool_def = self.registry.get_tool(tool_name)
        if not tool_def:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' is not registered in the Skills Registry.",
                duration_ms=round(duration_ms, 2),
                permission_used=PermissionLevel.READ_ONLY,
            )

        if not tool_def.enabled:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' is disabled in configuration.",
                duration_ms=round(duration_ms, 2),
                permission_used=tool_def.permission,
            )

        handler = self.registry.get_handler(tool_name)
        if not handler:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=f"Handler for tool '{tool_name}' is not available.",
                duration_ms=round(duration_ms, 2),
                permission_used=tool_def.permission,
            )

        # 1. Permission and Approval Gate
        requires_approval = (
            tool_def.requires_approval
            or tool_def.permission in (PermissionLevel.LOCAL_WRITE, PermissionLevel.EXTERNAL_WRITE)
            or tool_def.risk == RiskLevel.HIGH
        )

        if requires_approval:
            if not request.approved_by_user:
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_msg = f"Permission denied: Tool '{tool_name}' requires explicit user approval."
                self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error=error_msg,
                    duration_ms=round(duration_ms, 2),
                    permission_used=tool_def.permission,
                )

            # Consequential tools requiring approval MUST supply an action-bound approval token
            if not request.approval_token:
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_msg = (
                    f"Permission denied: Consequential tool '{tool_name}' requires a valid action-bound "
                    "approval token. A client-side boolean alone cannot authorize execution."
                )
                self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error=error_msg,
                    duration_ms=round(duration_ms, 2),
                    permission_used=tool_def.permission,
                )

            # Verify action-bound approval token strictly matches this action and payload
            is_valid, reason = verify_action_token(
                tool_name=tool_name,
                arguments=request.arguments,
                provided_token=request.approval_token,
                session_id=request.session_id,
            )
            if not is_valid:
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_msg = (
                    f"Permission denied: Action-bound approval token mismatch for tool '{tool_name}'. "
                    f"{reason}"
                )
                self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error=error_msg,
                    duration_ms=round(duration_ms, 2),
                    permission_used=tool_def.permission,
                )

            is_replayed = False
            with self._lock:
                if request.approval_token in self._consumed_tokens:
                    is_replayed = True
                else:
                    self._consumed_tokens.add(request.approval_token)

            if is_replayed:
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_msg = (
                    f"Permission denied: Action-bound approval token for tool '{tool_name}' "
                    "has already been consumed (replay detected)."
                )
                self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error=error_msg,
                    duration_ms=round(duration_ms, 2),
                    permission_used=tool_def.permission,
                )

        elif request.approval_token:
            # If an approval token was passed for any tool, verify and consume it atomically
            is_valid, reason = verify_action_token(
                tool_name=tool_name,
                arguments=request.arguments,
                provided_token=request.approval_token,
                session_id=request.session_id,
            )
            if not is_valid:
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_msg = (
                    f"Permission denied: Action-bound approval token mismatch for tool '{tool_name}'. "
                    f"{reason}"
                )
                self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error=error_msg,
                    duration_ms=round(duration_ms, 2),
                    permission_used=tool_def.permission,
                )

            is_replayed = False
            with self._lock:
                if request.approval_token in self._consumed_tokens:
                    is_replayed = True
                else:
                    self._consumed_tokens.add(request.approval_token)

            if is_replayed:
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_msg = (
                    f"Permission denied: Action-bound approval token for tool '{tool_name}' "
                    "has already been consumed (replay detected)."
                )
                self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error=error_msg,
                    duration_ms=round(duration_ms, 2),
                    permission_used=tool_def.permission,
                )

        # 2. Rate Limiting Gate
        if not self._check_rate_limit(tool_name, tool_def.rate_limit_per_minute):
            duration_ms = (time.perf_counter() - start_time) * 1000
            error_msg = f"Rate limit exceeded: Tool '{tool_name}' exceeds {tool_def.rate_limit_per_minute} calls/min."
            self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=error_msg,
                duration_ms=round(duration_ms, 2),
                permission_used=tool_def.permission,
            )

        # 3. Input Validation
        validated_args: Dict[str, Any] = {}
        if tool_def.input_model:
            try:
                parsed_model = tool_def.input_model.model_validate(request.arguments)
                validated_args = parsed_model.model_dump()
            except ValidationError as ve:
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_msg = f"Input validation failed for tool '{tool_name}': {ve}"
                self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error=error_msg,
                    duration_ms=round(duration_ms, 2),
                    permission_used=tool_def.permission,
                )
        else:
            validated_args = request.arguments

        # 4. Invocation with Timeout
        try:
            if inspect.iscoroutinefunction(handler):
                coro = handler(**validated_args)
            else:
                coro = asyncio.to_thread(handler, **validated_args)

            raw_result = await asyncio.wait_for(coro, timeout=tool_def.timeout_seconds)

            # Output validation / serialization
            if hasattr(raw_result, "model_dump"):
                result_dict = raw_result.model_dump()
            elif isinstance(raw_result, dict):
                result_dict = raw_result
            else:
                result_dict = {"output": raw_result}

            if tool_def.output_model and not hasattr(raw_result, "model_dump"):
                parsed_output = tool_def.output_model.model_validate(result_dict)
                result_dict = parsed_output.model_dump()

            # Sanitize and redact any secrets from result
            sanitized_result = self._sanitize_data(result_dict)

            duration_ms = (time.perf_counter() - start_time) * 1000
            self._record_audit(tool_name, True, duration_ms, request.session_id, tool_def.permission)

            return ToolExecutionResult(
                success=True,
                tool_name=tool_name,
                result=sanitized_result,
                duration_ms=round(duration_ms, 2),
                permission_used=tool_def.permission,
            )

        except asyncio.TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            error_msg = f"Tool execution timed out after {tool_def.timeout_seconds} seconds."
            self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=error_msg,
                duration_ms=round(duration_ms, 2),
                permission_used=tool_def.permission,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            error_msg = redact_secrets(f"Execution error in tool '{tool_name}': {str(exc)}")
            logger.error(error_msg, exc_info=True)
            self._record_audit(tool_name, False, duration_ms, request.session_id, tool_def.permission, error_msg)
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=error_msg,
                duration_ms=round(duration_ms, 2),
                permission_used=tool_def.permission,
            )

    def _record_audit(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        session_id: Optional[str],
        permission: PermissionLevel,
        error: Optional[str] = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "success": success,
            "duration_ms": round(duration_ms, 2),
            "session_id": session_id,
            "permission": permission.value,
            "error": error,
        }
        with self._lock:
            self.audit_log.append(entry)
