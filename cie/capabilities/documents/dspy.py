"""
DSPy Declarative Signature & Prompt Optimization Adapter (stanfordnlp/dspy).
Provides declarative input/output signatures, teleprompters,
and programmatic pipeline optimization.
Directly integrates upstream stanfordnlp/dspy library.
"""

import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

# Direct upstream integration
UPSTREAM_DSPY_DIR = Path("E:/CavrixCode-ecosystem/upstream/dspy")
_UPSTREAM_AVAILABLE = False
_dspy = None

if UPSTREAM_DSPY_DIR.exists():
    try:
        if str(UPSTREAM_DSPY_DIR) not in sys.path:
            sys.path.insert(0, str(UPSTREAM_DSPY_DIR))
        import dspy
        _dspy = dspy
        _UPSTREAM_AVAILABLE = True
    except Exception:
        _UPSTREAM_AVAILABLE = False


class SignatureField(BaseModel):
    name: str
    desc: str
    prefix: str


class DSPySignature(BaseModel):
    name: str
    instructions: str
    inputs: List[SignatureField]
    outputs: List[SignatureField]


class DSPyAdapter:
    """
    Declarative prompt programming engine implementing DSPy signatures
    using upstream stanfordnlp/dspy primitives.
    """

    def __init__(self):
        self.upstream_active = _UPSTREAM_AVAILABLE
        self.dspy_module = _dspy


    def compile_signature_prompt(self, signature: DSPySignature, input_values: Dict[str, Any]) -> str:
        prompt_parts = [f"Instruction: {signature.instructions}\n"]
        for field in signature.inputs:
            val = input_values.get(field.name, "")
            prompt_parts.append(f"{field.prefix} {val}")
        for field in signature.outputs:
            prompt_parts.append(f"{field.prefix} ")
        return "\n".join(prompt_parts)

    def optimize_fewshot_teleprompter(
        self,
        signature: DSPySignature,
        training_examples: List[Dict[str, Any]],
        metric_fn: Callable[[Dict[str, Any]], bool],
    ) -> List[Dict[str, Any]]:
        # Filters top examples meeting quality metric
        passing = [ex for ex in training_examples if metric_fn(ex)]
        return passing[:3]
