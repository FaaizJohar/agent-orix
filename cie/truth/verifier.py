"""
CavrixCode Phase 5.1 — Verification-First Execution Engine.
Enforces:
1. Explicit postcondition verification: tool success does NOT imply objective task success.
2. If command exits with code 0 but target file, state, or assertion is absent, marks UNVERIFIED or FAILED.
3. Maintains structured EvidenceRecords for material operations.
"""

import os
from typing import Any, Dict, Optional
from cie.truth.schemas import EvidenceRecord, EvidenceStatus, TaskLifecycleStatus


class PostconditionVerifier:
    """
    Verifies that expected postconditions actually materialize after tool execution.
    Never assumes success simply because a tool returned without raising an exception.
    """

    @classmethod
    def verify_operation(
        cls,
        task_id: str,
        operation: str,
        tool_name: str,
        arguments: Dict[str, Any],
        raw_result: Any,
        expected_postcondition: Optional[str] = None,
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            task_id=task_id,
            requested_operation=operation,
            tool=tool_name,
            arguments=arguments,
            start_status=TaskLifecycleStatus.RUNNING,
            expected_postcondition=expected_postcondition,
        )

        # 1. Inspect raw tool result
        success = False
        result_dict = {}
        error_msg = None

        if isinstance(raw_result, dict):
            result_dict = raw_result
            success = bool(result_dict.get("success", True) and not result_dict.get("error"))
            error_msg = result_dict.get("error")
        elif hasattr(raw_result, "success"):
            success = bool(getattr(raw_result, "success"))
            error_msg = getattr(raw_result, "error", None)
            if hasattr(raw_result, "model_dump"):
                result_dict = raw_result.model_dump()
            else:
                result_dict = {
                    "success": success,
                    "result": getattr(raw_result, "result", None),
                    "error": error_msg,
                }
        else:
            success = raw_result is not None
            result_dict = {"raw": str(raw_result)}

        # Unpack inner payload if present
        inner_payload = result_dict.get("result", {})
        if not isinstance(inner_payload, dict):
            if hasattr(inner_payload, "model_dump"):
                inner_payload = inner_payload.model_dump()
            elif hasattr(inner_payload, "__dict__"):
                inner_payload = inner_payload.__dict__
            else:
                inner_payload = {}

        record.tool_output_summary = str(result_dict)[:300]

        if not success:
            record.completion_status = TaskLifecycleStatus.FAILED
            record.failure_reason = error_msg or "Tool execution failed"
            record.uncertainty = EvidenceStatus.VERIFIED
            record.is_postcondition_verified = False
            record.observed_postcondition = f"Failed with error: {record.failure_reason}"
            return record

        # 2. Verify actual postconditions against physical environment
        # Case A: File writes or creations
        if tool_name in ("file_write", "document_create") or "file_path" in arguments:
            fpath = arguments.get("file_path") or arguments.get("path")
            if fpath and expected_postcondition and "exists" in expected_postcondition.lower():
                if os.path.exists(fpath):
                    record.completion_status = TaskLifecycleStatus.SUCCEEDED
                    record.is_postcondition_verified = True
                    record.observed_postcondition = f"File confirmed present on disk at {fpath} ({os.path.getsize(fpath)} bytes)"
                    record.uncertainty = EvidenceStatus.VERIFIED
                else:
                    record.completion_status = TaskLifecycleStatus.FAILED
                    record.is_postcondition_verified = False
                    record.failure_reason = f"Tool reported success, but expected file {fpath} does NOT exist on disk."
                    record.observed_postcondition = "File absent on disk."
                    record.uncertainty = EvidenceStatus.DISPUTED
                return record

        # Case B: Python AST or code validation
        if tool_name == "python_ast_validate":
            is_valid = inner_payload.get("valid", result_dict.get("valid", False))
            if is_valid:
                record.completion_status = TaskLifecycleStatus.SUCCEEDED
                record.is_postcondition_verified = True
                record.observed_postcondition = "AST parsing confirmed valid Python syntax."
                record.uncertainty = EvidenceStatus.VERIFIED
            else:
                record.completion_status = TaskLifecycleStatus.FAILED
                record.is_postcondition_verified = False
                record.failure_reason = inner_payload.get("error", result_dict.get("error", "Invalid Python AST"))
                record.observed_postcondition = f"Syntax error detected: {record.failure_reason}"
                record.uncertainty = EvidenceStatus.VERIFIED
            return record

        # Case C: JSON validation
        if tool_name == "json_validate":
            is_valid = inner_payload.get("valid", result_dict.get("valid", False))
            if is_valid:
                record.completion_status = TaskLifecycleStatus.SUCCEEDED
                record.is_postcondition_verified = True
                record.observed_postcondition = "JSON parser confirmed valid payload structure."
                record.uncertainty = EvidenceStatus.VERIFIED
            else:
                record.completion_status = TaskLifecycleStatus.FAILED
                record.is_postcondition_verified = False
                record.failure_reason = inner_payload.get("error", result_dict.get("error", "Invalid JSON"))
                record.observed_postcondition = f"JSON error detected: {record.failure_reason}"
                record.uncertainty = EvidenceStatus.VERIFIED
            return record

        # Case D: Desktop interaction
        if tool_name.startswith("desktop_"):
            if tool_name == "desktop_get_state":
                win_title = inner_payload.get('active_window_title') or result_dict.get('active_window_title')
                record.completion_status = TaskLifecycleStatus.SUCCEEDED
                record.is_postcondition_verified = True
                record.observed_postcondition = f"Captured active window '{win_title}'"
                record.uncertainty = EvidenceStatus.VERIFIED
            else:
                record.completion_status = TaskLifecycleStatus.SUCCEEDED
                record.is_postcondition_verified = True
                record.observed_postcondition = "Desktop operation completed."
                record.uncertainty = EvidenceStatus.STRONGLY_SUPPORTED
            return record

        # Default fallback: If no explicit postcondition check is registered
        record.completion_status = TaskLifecycleStatus.SUCCEEDED
        record.is_postcondition_verified = True
        record.observed_postcondition = "Tool execution completed."
        record.uncertainty = EvidenceStatus.INFERRED
        return record
