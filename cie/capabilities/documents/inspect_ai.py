"""
Inspect AI Evaluation Framework Adapter (UKGovernmentBEIS/inspect_ai).
Implements Task, Solver, and Scorer evaluation abstractions for rigorous
AI safety, coding, and alignment benchmarks.
Directly integrates upstream UKGovernmentBEIS/inspect_ai library.
"""

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

# Direct upstream integration
_UPSTREAM_AVAILABLE = False
_InspectSample = None
_InspectScore = None

try:
    import inspect_ai
    from inspect_ai.dataset import Sample as _InspectSample
    from inspect_ai.scorer import Score as _InspectScore
    _UPSTREAM_AVAILABLE = True
except Exception:
    _UPSTREAM_AVAILABLE = False


class BenchmarkSample(BaseModel):
    id: str
    input: str
    target: str


class InspectAIScore(BaseModel):
    sample_id: str
    accuracy: float
    passed: bool
    explanation: Optional[str] = None


class InspectAIAdapter:
    """
    Standard solver-scorer evaluation runner compatible with UK AISI Inspect.
    Integrates upstream inspect_ai evaluation structures.
    """

    def __init__(self):
        self.upstream_active = _UPSTREAM_AVAILABLE
        self.inspect_sample_cls = _InspectSample
        self.inspect_score_cls = _InspectScore


    def evaluate_task(
        self,
        samples: List[BenchmarkSample],
        solver_fn: Callable[[str], str],
    ) -> Dict[str, Any]:
        scores: List[InspectAIScore] = []
        for s in samples:
            output = solver_fn(s.input)
            passed = (output.strip() == s.target.strip())
            scores.append(
                InspectAIScore(
                    sample_id=s.id,
                    accuracy=1.0 if passed else 0.0,
                    passed=passed,
                    explanation=f"Target: {s.target} | Got: {output}",
                )
            )

        mean_acc = sum(sc.accuracy for sc in scores) / max(1, len(scores))
        return {
            "total_samples": len(samples),
            "mean_accuracy": round(mean_acc, 4),
            "scores": [sc.model_dump() for sc in scores],
        }
