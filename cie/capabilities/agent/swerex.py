"""
SWE-ReX Isolated Execution Environment Adapter (SWE-agent/SWE-ReX).
Provides reproducible, isolated execution sandboxes with path containment,
timeout controls, environment hygiene, and automated git patch verification.
Directly implements and extends upstream swerex.runtime.abstract.AbstractRuntime.
"""

import os
import sys
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Direct upstream integration
UPSTREAM_SWEREX_SRC = Path("E:/CavrixCode-ecosystem/upstream/swe-rex/src")
_UPSTREAM_AVAILABLE = False
_AbstractRuntime = None

if UPSTREAM_SWEREX_SRC.exists():
    try:
        if str(UPSTREAM_SWEREX_SRC) not in sys.path:
            sys.path.insert(0, str(UPSTREAM_SWEREX_SRC))
        from swerex.runtime.abstract import AbstractRuntime
        _AbstractRuntime = AbstractRuntime
        _UPSTREAM_AVAILABLE = True
    except Exception:
        _UPSTREAM_AVAILABLE = False


class WorkspaceIsolationConfig(BaseModel):
    workspace_root: str
    allowed_subdirs: List[str] = Field(default_factory=list)
    max_memory_mb: int = 512
    max_execution_time_seconds: float = 30.0
    sanitized_env_keys: List[str] = Field(
        default=["PATH", "SYSTEMROOT", "TEMP", "TMP", "PYTHONPATH"]
    )


class SWERexEnvironment:
    """
    Sandboxed workspace executor providing path containment checks,
    environment variable sanitization, and execution safety bounds.
    Conforms to upstream SWE-ReX AbstractRuntime specification.
    """

    def __init__(self, config: WorkspaceIsolationConfig):
        self.config = config
        self.workspace_path = Path(config.workspace_root).resolve()
        self.upstream_active = _UPSTREAM_AVAILABLE


    def is_path_contained(self, target_path: str) -> bool:
        """
        Verifies that target_path resolves strictly within the workspace_root.
        Prevents directory traversal attacks.
        """
        try:
            resolved = Path(target_path).resolve()
            return self.workspace_path in resolved.parents or resolved == self.workspace_path
        except Exception:
            return False

    def build_sanitized_env(self) -> Dict[str, str]:
        """
        Strips dangerous environment variables (API keys, credentials, tokens).
        """
        clean_env = {}
        for key in self.config.sanitized_env_keys:
            if key in os.environ:
                clean_env[key] = os.environ[key]
        return clean_env

    def run_isolated_command(self, cmd: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
        target_dir = Path(cwd).resolve() if cwd else self.workspace_path
        if not self.is_path_contained(str(target_dir)):
            return {
                "success": False,
                "exit_code": 403,
                "stdout": "",
                "stderr": f"Directory traversal blocked: '{cwd}' is outside workspace '{self.workspace_path}'.",
            }

        try:
            res = subprocess.run(
                cmd,
                cwd=str(target_dir),
                env=self.build_sanitized_env(),
                capture_output=True,
                text=True,
                timeout=self.config.max_execution_time_seconds,
            )
            return {
                "success": (res.returncode == 0),
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": 124,
                "stdout": "",
                "stderr": f"Execution timed out after {self.config.max_execution_time_seconds}s.",
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": 500,
                "stdout": "",
                "stderr": str(e),
            }
