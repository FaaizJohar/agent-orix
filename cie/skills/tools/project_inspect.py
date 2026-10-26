"""
Python Project Inspection Tool.
Inspects Python project structure, build metadata, configuration files, and virtual environment status.
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field


class PythonProjectInspectInput(BaseModel):
    project_dir: str = Field(default=".", description="Path to Python project root directory")


class PythonProjectInspectOutput(BaseModel):
    is_python_project: bool
    project_name: Optional[str] = None
    build_system: Optional[str] = None
    config_files: List[str] = Field(default_factory=list)
    has_virtualenv: bool = False
    has_tests: bool = False
    has_git: bool = False
    python_files_count: int = 0
    error: Optional[str] = None


def python_project_inspect(project_dir: str = ".") -> PythonProjectInspectOutput:
    """
    Inspects project configuration files and structure without executing any scripts.
    """
    abs_path = os.path.abspath(project_dir)
    if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
        return PythonProjectInspectOutput(
            is_python_project=False,
            error=f"Directory '{project_dir}' does not exist or is not a directory.",
        )

    config_names = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "tox.ini",
        ".python-version",
    ]

    found_configs = []
    for c in config_names:
        if os.path.isfile(os.path.join(abs_path, c)):
            found_configs.append(c)

    has_git = os.path.isdir(os.path.join(abs_path, ".git"))
    has_virtualenv = any(
        os.path.isdir(os.path.join(abs_path, d)) for d in [".venv", "venv", "env", ".env"]
    )
    has_tests = any(
        os.path.isdir(os.path.join(abs_path, d)) for d in ["tests", "test"]
    )

    build_system = None
    project_name = None

    # Parse pyproject.toml if present
    pyproject_path = os.path.join(abs_path, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        try:
            import tomllib  # Python 3.11+ standard library
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                build_system = data.get("build-system", {}).get("build-backend")
                project_name = data.get("project", {}).get("name")
        except Exception:
            pass

    # Count python files (bounded)
    py_count = 0
    for root, dirs, files in os.walk(abs_path):
        # Skip hidden and cache folders
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules")]
        for f in files:
            if f.endswith(".py"):
                py_count += 1
                if py_count >= 1000:
                    break
        if py_count >= 1000:
            break

    is_py = len(found_configs) > 0 or py_count > 0

    return PythonProjectInspectOutput(
        is_python_project=is_py,
        project_name=project_name or os.path.basename(abs_path),
        build_system=build_system,
        config_files=found_configs,
        has_virtualenv=has_virtualenv,
        has_tests=has_tests,
        has_git=has_git,
        python_files_count=py_count,
        error=None,
    )
