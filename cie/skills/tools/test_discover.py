"""
Test Discovery Tool.
Discovers unit and integration test files, suites, and test cases without running any code.
"""

import ast
import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field


class TestDiscoverInput(BaseModel):
    directory_path: str = Field(default=".", description="Root directory to search for tests")


class TestCaseInfo(BaseModel):
    file_path: str
    test_functions: List[str] = Field(default_factory=list)
    test_classes: List[str] = Field(default_factory=list)


class TestDiscoverOutput(BaseModel):
    test_files_count: int
    test_cases_count: int
    test_files: List[str] = Field(default_factory=list)
    test_details: List[TestCaseInfo] = Field(default_factory=list)
    frameworks_detected: List[str] = Field(default_factory=list)
    error: Optional[str] = None


def test_discover(directory_path: str = ".") -> TestDiscoverOutput:
    """
    Statically discovers tests by inspecting file patterns and AST nodes.
    Zero code execution.
    """
    abs_dir = os.path.abspath(directory_path)
    if not os.path.exists(abs_dir) or not os.path.isdir(abs_dir):
        return TestDiscoverOutput(
            test_files_count=0,
            test_cases_count=0,
            error=f"Directory '{directory_path}' does not exist.",
        )

    test_files: List[str] = []
    for root, dirs, files in os.walk(abs_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", "venv", ".venv")]
        for f in files:
            if (f.startswith("test_") or f.endswith("_test.py")) and f.endswith(".py"):
                test_files.append(os.path.join(root, f))
                if len(test_files) >= 200:
                    break
        if len(test_files) >= 200:
            break

    details: List[TestCaseInfo] = []
    total_cases = 0
    frameworks = set()

    for t_file in test_files:
        rel_path = os.path.relpath(t_file, abs_dir)
        funcs: List[str] = []
        classes: List[str] = []

        try:
            with open(t_file, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()

            if "pytest" in code:
                frameworks.add("pytest")
            if "unittest" in code:
                frameworks.add("unittest")

            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_") or node.name.endswith("_test"):
                        funcs.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    if node.name.startswith("Test") or node.name.endswith("Test") or node.name.endswith("Tests"):
                        classes.append(node.name)
        except Exception:
            pass

        total_cases += len(funcs)
        details.append(
            TestCaseInfo(
                file_path=rel_path,
                test_functions=funcs,
                test_classes=classes,
            )
        )

    return TestDiscoverOutput(
        test_files_count=len(test_files),
        test_cases_count=total_cases,
        test_files=[os.path.relpath(f, abs_dir) for f in test_files],
        test_details=details[:50],
        frameworks_detected=sorted(list(frameworks)),
        error=None,
    )
