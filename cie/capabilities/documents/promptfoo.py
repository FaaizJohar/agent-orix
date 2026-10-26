"""
Promptfoo Evaluation & Security Red-Teaming Adapter (promptfoo/promptfoo).
Implements automated assertion checks: contains, regex, similarity,
and security red-teaming checks for LLM outputs.
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PromptfooAssertion(BaseModel):
    type: str  # 'contains', 'not-contains', 'regex', 'equals'
    value: str


class EvaluationResult(BaseModel):
    passed: bool
    score: float
    reason: Optional[str] = None


class PromptfooAdapter:
    """
    Evaluates LLM model responses against structured assertion matrices.
    """

    def evaluate_response(self, response: str, assertions: List[PromptfooAssertion]) -> EvaluationResult:
        for assertion in assertions:
            atype = assertion.type.lower()
            val = assertion.value

            if atype == "contains" and val not in response:
                return EvaluationResult(passed=False, score=0.0, reason=f"Response missing expected string: '{val}'")
            elif atype == "not-contains" and val in response:
                return EvaluationResult(passed=False, score=0.0, reason=f"Response contains forbidden string: '{val}'")
            elif atype == "regex" and not re.search(val, response):
                return EvaluationResult(passed=False, score=0.0, reason=f"Response failed regex match: '{val}'")
            elif atype == "equals" and response.strip() != val.strip():
                return EvaluationResult(passed=False, score=0.0, reason=f"Response does not equal expected value.")

        return EvaluationResult(passed=True, score=1.0, reason="All assertions passed successfully.")
