"""
Outcome verification and error classification engine for CIE Plan Execution.
Ensures tool execution is verified against expected semantic outputs rather than
blindly relying on exception-free returns.
"""

import re
from typing import Any, Dict, Optional, Tuple

from cie.planning.schemas import ErrorCategory, PlanStep
from cie.skills.schemas import ToolExecutionResult


class PlanVerifier:
    """
    Validates tool execution outcomes against domain-specific expectations
    and classifies failures into actionable error categories.
    """

    @staticmethod
    def classify_error(error_msg: Optional[str]) -> ErrorCategory:
        if not error_msg:
            return ErrorCategory.EXECUTION_ERROR

        lower = error_msg.lower()

        # Security violations (Immediate abort, non-retryable)
        if any(term in lower for term in [
            "ssrf", "private ip", "loopback", "metadata", "forbidden scheme",
            "security restriction", "path traversal", "sensitive file", "argument injection",
            "access denied by security", "boundary violation"
        ]):
            return ErrorCategory.SECURITY_VIOLATION

        # User consent / permission required
        if any(term in lower for term in ["approval required", "action-bound approval token", "permission denied"]):
            return ErrorCategory.PERMISSION_DENIED

        # Input schema / validation error
        if any(term in lower for term in ["input validation failed", "validation error", "missing required", "invalid argument", "1 validation error"]):
            return ErrorCategory.VALIDATION_ERROR

        # Resource not found
        if any(term in lower for term in ["not found", "no such file", "does not exist", "not a git repository"]):
            return ErrorCategory.NOT_FOUND

        # Transient / network timeout (potentially retryable if read-only)
        if any(term in lower for term in ["timeout", "timed out", "connection reset", "temporary failure", "rate limit exceeded"]):
            return ErrorCategory.TRANSIENT_NETWORK

        return ErrorCategory.EXECUTION_ERROR

    def verify_step_outcome(
        self,
        step: PlanStep,
        exec_result: ToolExecutionResult,
    ) -> Tuple[bool, Optional[str]]:
        """
        Performs semantic verification of a tool execution result.
        Returns (is_verified: bool, error_reason: Optional[str]).
        """
        # 1. Base success check from executor
        if not exec_result.success:
            return False, exec_result.error or "Tool execution returned success=False."

        result_data = exec_result.result or {}

        # 2. Check for tool-level error fields
        if result_data.get("error"):
            return False, f"Tool reported internal error: {result_data.get('error')}"

        # 3. Domain-specific verification checks
        tool_name = step.skill_id

        if tool_name == "python_ast_validate":
            if "valid" not in result_data:
                return False, "AST validator result missing 'valid' boolean field."

        elif tool_name == "json_validate":
            if "valid" not in result_data or "data_type" not in result_data:
                return False, "JSON validator result missing structure or validity fields."

        elif tool_name == "yaml_validate":
            if "valid" not in result_data:
                return False, "YAML validator result missing 'valid' field."

        elif tool_name == "markdown_check":
            if "valid" not in result_data or "headings_count" not in result_data:
                return False, "Markdown checker missing heading count or validity metrics."

        elif tool_name in ("git_status", "git_diff_summary"):
            if "is_git_repo" not in result_data:
                return False, "Git tool output missing 'is_git_repo' indicator."

        elif tool_name == "file_tree_inspect":
            if "tree" not in result_data:
                return False, "File tree inspect result missing 'tree' structure."

        elif tool_name == "file_read_text":
            if "content" not in result_data or "lines_returned" not in result_data:
                return False, "File read result missing content or lines_returned fields."

        elif tool_name == "file_search_text":
            if "matches" not in result_data or "matches_count" not in result_data:
                return False, "File search result missing matches or matches_count fields."

        elif tool_name == "document_extract_text":
            if "format" not in result_data or "total_characters" not in result_data:
                return False, "Document text extractor missing format or total_characters."

        elif tool_name == "document_qa":
            if "answer" not in result_data or "has_sufficient_evidence" not in result_data:
                return False, "Document QA result missing answer or evidence determination."

        elif tool_name == "file_integrity_verify":
            sha = result_data.get("sha256")
            if not sha or len(sha) != 64 or not re.match(r"^[0-9a-fA-F]{64}$", sha):
                return False, f"File integrity check returned invalid SHA-256 hash: {sha}"

        elif tool_name == "http_endpoint_check":
            if "accessible" not in result_data:
                return False, "HTTP check missing accessibility indicator."

        elif tool_name == "dependency_inspect":
            if "dependencies" not in result_data:
                return False, "Dependency inspect missing dependency listing."

        elif tool_name == "test_discover":
            if "test_files" not in result_data or "total_test_files" not in result_data:
                return False, "Test discovery missing test file statistics."

        elif tool_name == "log_parse_errors":
            if "error_count" not in result_data or "errors" not in result_data:
                return False, "Log parser missing error count or extracted errors list."

        elif tool_name == "browser_open":
            if "current_url" not in result_data or "status_code" not in result_data:
                return False, "Browser open result missing current_url or status_code."
            if result_data.get("status_code", 0) >= 400:
                return False, f"Browser navigation returned HTTP error status {result_data.get('status_code')}."

        elif tool_name == "browser_back":
            if "success" not in result_data or not result_data.get("success"):
                return False, "Browser back navigation failed or missing success indicator."

        elif tool_name == "browser_get_page_snapshot":
            if "accessibility_tree" not in result_data or "interactive_elements" not in result_data:
                return False, "Browser snapshot missing accessibility_tree or interactive_elements."

        elif tool_name == "browser_find_text":
            if "found" not in result_data or "matches_count" not in result_data:
                return False, "Browser find text missing found flag or matches_count."

        elif tool_name == "browser_click_element":
            if not result_data.get("success", False):
                return False, result_data.get("error") or "Browser click element failed."

        elif tool_name == "browser_fill_field":
            if not result_data.get("success", False):
                return False, result_data.get("error") or "Browser fill field failed."

        elif tool_name == "browser_select_option":
            if not result_data.get("success", False):
                return False, result_data.get("error") or "Browser select option failed."

        elif tool_name == "browser_list_tabs":
            if "tabs" not in result_data or "active_tab_index" not in result_data:
                return False, "Browser tab list missing tabs array or active_tab_index."

        elif tool_name == "browser_switch_tab":
            if not result_data.get("success", False):
                return False, result_data.get("error") or "Browser tab switch failed."

        elif tool_name == "browser_close_tab":
            if not result_data.get("success", False):
                return False, result_data.get("error") or "Browser tab close failed."

        elif tool_name == "browser_take_screenshot":
            if "file_path" not in result_data or not result_data.get("file_path"):
                return False, "Browser screenshot missing valid file_path."

        elif tool_name == "browser_wait_for_text":
            if not result_data.get("appeared", False):
                return False, result_data.get("error") or f"Expected text '{result_data.get('text')}' did not appear."

        # Desktop Automation Tool Verifications
        elif tool_name == "desktop_get_state":
            if "screen_resolution" not in result_data:
                return False, "Desktop get state missing screen_resolution metric."

        elif tool_name == "desktop_list_windows":
            if "windows" not in result_data or "total_windows" not in result_data:
                return False, "Desktop list windows missing windows collection or total count."

        elif tool_name == "desktop_screenshot":
            if "file_path" not in result_data or not result_data.get("file_path"):
                return False, "Desktop screenshot missing valid file_path."

        elif tool_name == "desktop_click":
            if not result_data.get("success", False):
                return False, result_data.get("error") or "Desktop click action failed."

        elif tool_name == "desktop_type_text":
            if not result_data.get("success", False):
                return False, result_data.get("error") or "Desktop type text action failed."

        elif tool_name == "desktop_keypress":
            if not result_data.get("success", False):
                return False, result_data.get("error") or "Desktop keypress action failed."

        elif tool_name == "desktop_wait_for_state":
            if not result_data.get("matched", False):
                return False, result_data.get("error") or "Desktop wait for state timed out or condition not met."

        # 4. Check explicit verification requirements attached to step
        if step.verification:
            # Check required keys
            for key in step.verification.required_keys:
                if key not in result_data:
                    return False, f"Verification failed: missing expected key '{key}' in tool result."

            # Check criteria matches
            for k, expected_val in step.verification.criteria.items():
                actual_val = result_data.get(k)
                if actual_val != expected_val:
                    return False, (
                        f"Verification failed: expected '{k}' to be {expected_val!r}, "
                        f"got {actual_val!r}."
                    )

        return True, None
