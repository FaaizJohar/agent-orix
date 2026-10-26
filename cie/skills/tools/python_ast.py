"""
Python AST Validation Tool.
Validates Python syntax and extracts AST structural metadata without code execution.
"""

import ast
from typing import List, Optional
from pydantic import BaseModel, Field


class PythonAstInput(BaseModel):
    code: str = Field(..., description="Python source code snippet to parse and validate")


class PythonAstOutput(BaseModel):
    valid: bool
    error: Optional[str] = None
    error_line: Optional[int] = None
    error_column: Optional[int] = None
    classes: List[str] = Field(default_factory=list)
    functions: List[str] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)


def python_ast_validate(code: str) -> PythonAstOutput:
    """
    Safely validates Python syntax using Python's built-in AST parser.
    Never evaluates or executes the code.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return PythonAstOutput(
            valid=False,
            error=str(e.msg),
            error_line=e.lineno,
            error_column=e.offset,
            classes=[],
            functions=[],
            imports=[],
        )
    except Exception as e:
        return PythonAstOutput(
            valid=False,
            error=f"AST parsing failed: {str(e)}",
            classes=[],
            functions=[],
            imports=[],
        )

    classes = []
    functions = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)

    return PythonAstOutput(
        valid=True,
        error=None,
        error_line=None,
        error_column=None,
        classes=sorted(list(set(classes))),
        functions=sorted(list(set(functions))),
        imports=sorted(list(set(imports))),
    )
