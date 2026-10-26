"""
Dependency Inspection Tool.
Extracts declared dependencies from requirements.txt, package.json, or pyproject.toml without running pip or npm.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DependencyInspectInput(BaseModel):
    file_path: str = Field(..., description="Path to dependency file (requirements.txt, package.json, or pyproject.toml)")


class DependencyItem(BaseModel):
    name: str
    specifier: str = ""


class DependencyInspectOutput(BaseModel):
    file_type: str
    dependencies_count: int
    dependencies: List[DependencyItem] = Field(default_factory=list)
    dev_dependencies: List[DependencyItem] = Field(default_factory=list)
    error: Optional[str] = None


from cie.skills.path_guard import validate_safe_path, is_sensitive_filename, PathSecurityError


def dependency_inspect(file_path: str) -> DependencyInspectOutput:
    """
    Safely inspects dependencies declared in a manifest file without invoking external tools.
    Enforces path security and blocks sensitive file inspection.
    """
    try:
        abs_path_obj = validate_safe_path(file_path, must_exist=True, must_be_file=True)
        abs_path = str(abs_path_obj)
    except PathSecurityError as pse:
        return DependencyInspectOutput(
            file_type="unknown",
            dependencies_count=0,
            error=f"Security restriction: {str(pse)}",
        )
    except Exception as e:
        return DependencyInspectOutput(
            file_type="unknown",
            dependencies_count=0,
            error=f"File '{file_path}' does not exist or is invalid: {str(e)}",
        )

    basename = os.path.basename(abs_path).lower()
    if is_sensitive_filename(basename):
        return DependencyInspectOutput(
            file_type="unknown",
            dependencies_count=0,
            error=f"Security restriction: Sensitive file '{basename}' cannot be inspected as a dependency manifest.",
        )

    if basename.endswith(".json") or basename == "package.json":
        return _inspect_package_json(abs_path)
    elif basename == "pyproject.toml":
        return _inspect_pyproject_toml(abs_path)
    elif "requirements" in basename or basename.endswith(".txt"):
        return _inspect_requirements_txt(abs_path)
    else:
        return DependencyInspectOutput(
            file_type="unsupported",
            dependencies_count=0,
            error=f"Manifest file '{basename}' is not supported.",
        )


def _inspect_requirements_txt(file_path: str) -> DependencyInspectOutput:
    dependencies: List[DependencyItem] = []
    req_pattern = re.compile(r"^([a-zA-Z0-9_\-\.]+)(.*)$")

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                sline = line.strip()
                if not sline or sline.startswith("#") or sline.startswith("-"):
                    continue
                m = req_pattern.match(sline)
                if m:
                    pkg_name = m.group(1).strip()
                    specifier = m.group(2).strip()
                    dependencies.append(DependencyItem(name=pkg_name, specifier=specifier))
    except Exception as e:
        return DependencyInspectOutput(file_type="requirements.txt", dependencies_count=0, error=str(e))

    return DependencyInspectOutput(
        file_type="requirements.txt",
        dependencies_count=len(dependencies),
        dependencies=dependencies,
        dev_dependencies=[],
    )


def _inspect_package_json(file_path: str) -> DependencyInspectOutput:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception as e:
        return DependencyInspectOutput(file_type="package.json", dependencies_count=0, error=str(e))

    deps: List[DependencyItem] = []
    dev_deps: List[DependencyItem] = []

    for name, spec in data.get("dependencies", {}).items():
        deps.append(DependencyItem(name=name, specifier=str(spec)))

    for name, spec in data.get("devDependencies", {}).items():
        dev_deps.append(DependencyItem(name=name, specifier=str(spec)))

    return DependencyInspectOutput(
        file_type="package.json",
        dependencies_count=len(deps) + len(dev_deps),
        dependencies=deps,
        dev_dependencies=dev_deps,
    )


def _inspect_pyproject_toml(file_path: str) -> DependencyInspectOutput:
    try:
        import tomllib
        with open(file_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return DependencyInspectOutput(file_type="pyproject.toml", dependencies_count=0, error=str(e))

    deps: List[DependencyItem] = []
    dev_deps: List[DependencyItem] = []

    req_pattern = re.compile(r"^([a-zA-Z0-9_\-\.]+)(.*)$")

    # [project.dependencies]
    project_deps = data.get("project", {}).get("dependencies", [])
    for line in project_deps:
        m = req_pattern.match(line.strip())
        if m:
            deps.append(DependencyItem(name=m.group(1).strip(), specifier=m.group(2).strip()))

    # [project.optional-dependencies]
    opt_deps = data.get("project", {}).get("optional-dependencies", {})
    for group, group_deps in opt_deps.items():
        for line in group_deps:
            m = req_pattern.match(line.strip())
            if m:
                dev_deps.append(DependencyItem(name=f"{m.group(1).strip()} ({group})", specifier=m.group(2).strip()))

    return DependencyInspectOutput(
        file_type="pyproject.toml",
        dependencies_count=len(deps) + len(dev_deps),
        dependencies=deps,
        dev_dependencies=dev_deps,
    )
