"""
Codebase Memory MCP AST Indexer & Contextual Retrieval Adapter (DeusData/codebase-memory-mcp).
Indexes AST definitions, classes, functions, and references across codebases
for context retrieval without full-file bloating.
"""

import ast
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SymbolDefinition(BaseModel):
    name: str
    symbol_type: str  # function, class, variable
    file_path: str
    line_number: int
    docstring: Optional[str] = None


class CodebaseMemoryMCPAdapter:
    """
    AST symbol parser and codebase indexer.
    """

    def __init__(self):
        self._symbols: Dict[str, List[SymbolDefinition]] = {}

    def index_python_source(self, file_path: str, source_code: str) -> List[SymbolDefinition]:
        try:
            tree = ast.parse(source_code)
        except Exception:
            return []

        indexed = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                sym = SymbolDefinition(
                    name=node.name,
                    symbol_type="function",
                    file_path=file_path,
                    line_number=node.lineno,
                    docstring=ast.get_docstring(node),
                )
                indexed.append(sym)
                self._symbols.setdefault(node.name.lower(), []).append(sym)
            elif isinstance(node, ast.ClassDef):
                sym = SymbolDefinition(
                    name=node.name,
                    symbol_type="class",
                    file_path=file_path,
                    line_number=node.lineno,
                    docstring=ast.get_docstring(node),
                )
                indexed.append(sym)
                self._symbols.setdefault(node.name.lower(), []).append(sym)

        return indexed

    def find_symbol(self, symbol_name: str) -> List[SymbolDefinition]:
        return self._symbols.get(symbol_name.lower(), [])
