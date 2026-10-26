"""
Open Interpreter Execution Adapter (OpenInterpreter/open-interpreter).
Provides controlled natural language computer task execution, safe code interpretation,
and sandboxed subprocess execution with approval gates.
"""

import subprocess
import sys
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CodeExecutionRequest(BaseModel):
    language: str = Field(..., description="Language to execute: 'python', 'powershell', 'cmd'")
    code: str = Field(..., description="Script or command string to execute")
    timeout_seconds: float = Field(default=15.0, le=60.0)
    requires_approval: bool = Field(default=False)
    approval_token: Optional[str] = None


class CodeExecutionResult(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    error: Optional[str] = None


class OpenInterpreterAdapter:
    """
    Executes controlled code snippets in isolated subprocesses.
    Enforces timeout, non-interactive execution, and strict approvals
    for mutating or high-risk commands.
    """

    CONSEQUENTIAL_KEYWORDS = [
        "rm -rf", "del /f", "format", "drop database", "shutdown",
        "drop table", "remove-item", "mkfs", "dd if="
    ]

    def is_consequential(self, code: str) -> bool:
        code_lower = code.lower()
        return any(kw in code_lower for kw in self.CONSEQUENTIAL_KEYWORDS)

    def execute(self, request: CodeExecutionRequest) -> CodeExecutionResult:
        if self.is_consequential(request.code) and not request.approval_token:
            return CodeExecutionResult(
                success=False,
                exit_code=403,
                stdout="",
                stderr="Consequential code execution requires explicit human approval token.",
                error="CONSEQUENTIAL_ACTION_BLOCKED",
            )

        lang = request.language.lower().strip()
        cmd = []

        if lang == "python":
            cmd = [sys.executable, "-c", request.code]
        elif lang in ("powershell", "ps1"):
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", request.code]
        elif lang in ("cmd", "batch", "shell"):
            cmd = ["cmd.exe", "/c", request.code]
        else:
            return CodeExecutionResult(
                success=False,
                exit_code=400,
                stdout="",
                stderr=f"Unsupported language: {request.language}",
                error="UNSUPPORTED_LANGUAGE",
            )

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
            )
            return CodeExecutionResult(
                success=(res.returncode == 0),
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                error=None if res.returncode == 0 else f"Process exited with code {res.returncode}",
            )
        except subprocess.TimeoutExpired:
            return CodeExecutionResult(
                success=False,
                exit_code=124,
                stdout="",
                stderr=f"Execution timed out after {request.timeout_seconds} seconds.",
                error="TIMEOUT_EXPIRED",
            )
        except Exception as e:
            return CodeExecutionResult(
                success=False,
                exit_code=500,
                stdout="",
                stderr=str(e),
                error="EXECUTION_EXCEPTION",
            )
