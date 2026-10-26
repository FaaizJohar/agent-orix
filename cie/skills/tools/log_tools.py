"""
Log Error Parsing Tool.
Parses application and build logs to extract errors, warnings, and stack traces with secret scrubbing.
"""

import os
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from cie.safety import redact_secrets


class LogParseErrorsInput(BaseModel):
    log_content_or_path: str = Field(..., description="Log text content or path to log file")
    is_path: bool = Field(default=False, description="Whether input is a file path")
    max_errors: int = Field(default=50, description="Maximum error entries to return")


class LogParseErrorsOutput(BaseModel):
    total_lines: int
    error_count: int
    warning_count: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    tracebacks: List[str] = Field(default_factory=list)
    error: Optional[str] = None


from cie.skills.path_guard import validate_safe_path, is_sensitive_filename, PathSecurityError


def log_parse_errors(
    log_content_or_path: str,
    is_path: bool = False,
    max_errors: int = 50,
) -> LogParseErrorsOutput:
    """
    Parses logs for ERROR, CRITICAL, WARNING, and Traceback blocks.
    Redacts any sensitive tokens and API keys. Enforces filesystem boundaries.
    """
    content = ""
    if is_path:
        try:
            path_obj = validate_safe_path(log_content_or_path, must_exist=True, must_be_file=True)
            path = str(path_obj)
        except PathSecurityError as pse:
            return LogParseErrorsOutput(
                total_lines=0,
                error_count=0,
                warning_count=0,
                error=f"Security restriction: {str(pse)}",
            )
        except Exception as e:
            return LogParseErrorsOutput(
                total_lines=0,
                error_count=0,
                warning_count=0,
                error=f"Log file '{log_content_or_path}' is invalid or does not exist: {str(e)}",
            )

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(500_000)  # Bound file read to 500 KB
        except Exception as e:
            return LogParseErrorsOutput(
                total_lines=0,
                error_count=0,
                warning_count=0,
                error=f"Failed to read log file: {str(e)}",
            )
    else:
        content = log_content_or_path

    lines = content.splitlines()
    error_pattern = re.compile(r"\b(ERROR|CRITICAL|FATAL)\b", re.IGNORECASE)
    warning_pattern = re.compile(r"\b(WARNING|WARN)\b", re.IGNORECASE)

    errors: List[Dict[str, Any]] = []
    tracebacks: List[str] = []
    warning_count = 0

    current_tb: List[str] = []
    in_tb = False

    for idx, line in enumerate(lines, 1):
        clean_line = redact_secrets(line)

        # Check for traceback
        if "Traceback (most recent call last):" in clean_line:
            in_tb = True
            current_tb = [clean_line]
            continue
        elif in_tb:
            current_tb.append(clean_line)
            # Traceback ends with an Exception or Error line that does not start with whitespace
            if re.match(r"^[A-Za-z0-9_]+(Error|Exception):", clean_line) or not clean_line.strip():
                if any(err in clean_line for err in ("Error", "Exception")):
                    tracebacks.append("\n".join(current_tb))
                in_tb = False
                current_tb = []
            continue

        if warning_pattern.search(clean_line):
            warning_count += 1

        if error_pattern.search(clean_line) and len(errors) < max_errors:
            errors.append({
                "line": idx,
                "text": clean_line[:300],
            })

    if in_tb and current_tb:
        tracebacks.append("\n".join(current_tb))

    return LogParseErrorsOutput(
        total_lines=len(lines),
        error_count=len(errors),
        warning_count=warning_count,
        errors=errors[:max_errors],
        tracebacks=tracebacks[:10],
        error=None,
    )
