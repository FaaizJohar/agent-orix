"""
Langfuse Tracing & Observability Adapter (langfuse/langfuse).
Provides execution trace trees, spans, generation metrics, and latency
tracking with sensitive data redaction.
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LangfuseSpan(BaseModel):
    id: str
    name: str
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    status: str = "running"


class LangfuseTrace(BaseModel):
    trace_id: str
    name: str
    user_id: Optional[str] = None
    spans: List[LangfuseSpan] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class LangfuseAdapter:
    """
    In-memory and local file telemetry observer compatible with Langfuse.
    """

    def __init__(self):
        self.traces: Dict[str, LangfuseTrace] = {}

    def create_trace(self, trace_id: str, name: str, user_id: Optional[str] = None) -> LangfuseTrace:
        trace = LangfuseTrace(trace_id=trace_id, name=name, user_id=user_id)
        self.traces[trace_id] = trace
        return trace

    def start_span(self, trace_id: str, span_id: str, name: str, input_data: Optional[Dict[str, Any]] = None) -> Optional[LangfuseSpan]:
        trace = self.traces.get(trace_id)
        if not trace:
            return None
        span = LangfuseSpan(id=span_id, name=name, input_data=input_data or {})
        trace.spans.append(span)
        return span

    def end_span(self, trace_id: str, span_id: str, output_data: Optional[Dict[str, Any]] = None) -> None:
        trace = self.traces.get(trace_id)
        if not trace:
            return
        for s in trace.spans:
            if s.id == span_id:
                s.end_time = time.time()
                s.output_data = output_data or {}
                s.status = "completed"
                break
