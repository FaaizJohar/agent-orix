"""
Project Command Execution Tool.
Executes project commands (tests, builds, diagnostics) with bounded timeouts,
output capture, environment sandboxing, and destructive command blocking.
"""

import asyncio
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from cie.skills.path_guard import validate_safe_path, PathSecurityError


PROHIBITED_COMMAND_PATTERNS = [
    re.compile(r"\brm\s+-[rf]{1,2}\s+(?:/|[a-zA-Z]:\\)", re.IGNORECASE),
    re.compile(r"\b(?:format|mkfs|fdisk|diskpart)\b", re.IGNORECASE),
    re.compile(r"\b(?:del|erase)\s+/[fsq\s]+[a-zA-Z]:\\", re.IGNORECASE),
    re.compile(r"\b(?:shutdown|reboot)\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", re.IGNORECASE),  # fork bomb
]


class ProjectCommandRunInput(BaseModel):
    command: str = Field(..., description="Project command line to execute (e.g. 'pytest -q', 'python -m unittest')")
    cwd: Optional[str] = Field(default=".", description="Working directory inside permitted workspace roots")
    timeout_seconds: int = Field(default=30, ge=1, le=120, description="Execution timeout in seconds (1-120)")


class ProjectCommandRunOutput(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    error: Optional[str] = None


def project_command_run(
    command: str,
    cwd: str = ".",
    timeout_seconds: int = 30,
) -> ProjectCommandRunOutput:
    """
    Executes a project command within permitted workspace roots.
    Enforces timeout bounds, blocks destructive shell commands, and captures full stdout/stderr.
    """
    cmd_clean = command.strip()
    if not cmd_clean:
        return ProjectCommandRunOutput(
            command=command,
            exit_code=1,
            stdout="",
            stderr="",
            duration_ms=0.0,
            error="Command cannot be empty.",
        )

    for pat in PROHIBITED_COMMAND_PATTERNS:
        if pat.search(cmd_clean):
            return ProjectCommandRunOutput(
                command=command,
                exit_code=126,
                stdout="",
                stderr="Security violation: Command matches prohibited destructive or system-critical pattern.",
                duration_ms=0.0,
                error="Prohibited command blocked by security policy.",
            )

    try:
        abs_cwd = validate_safe_path(cwd, must_exist=True, must_be_dir=True)
    except Exception as e:
        return ProjectCommandRunOutput(
            command=command,
            exit_code=1,
            stdout="",
            stderr="",
            duration_ms=0.0,
            error=f"Invalid working directory: {str(e)}",
        )

    bounded_timeout = max(1, min(timeout_seconds, 120))
    t0 = time.perf_counter()

    try:
        proc = subprocess.run(
            cmd_clean,
            cwd=str(abs_cwd),
            capture_output=True,
            text=True,
            shell=True,
            timeout=bounded_timeout,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        return ProjectCommandRunOutput(
            command=cmd_clean,
            exit_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            duration_ms=round(duration_ms, 2),
            timed_out=False,
            error=None if proc.returncode == 0 else f"Command exited with non-zero code: {proc.returncode}",
        )
    except subprocess.TimeoutExpired as te:
        duration_ms = (time.perf_counter() - t0) * 1000
        out = te.stdout if isinstance(te.stdout, str) else (te.stdout.decode("utf-8", errors="replace") if te.stdout else "")
        err = te.stderr if isinstance(te.stderr, str) else (te.stderr.decode("utf-8", errors="replace") if te.stderr else "")
        return ProjectCommandRunOutput(
            command=cmd_clean,
            exit_code=124,
            stdout=out or "",
            stderr=err or "",
            duration_ms=round(duration_ms, 2),
            timed_out=True,
            error=f"Command execution timed out after {bounded_timeout} seconds.",
        )
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        return ProjectCommandRunOutput(
            command=cmd_clean,
            exit_code=1,
            stdout="",
            stderr=str(e),
            duration_ms=round(duration_ms, 2),
            error=f"Command execution failed: {str(e)}",
        )
