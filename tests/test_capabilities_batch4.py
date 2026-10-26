"""
Tests for CavrixCode Phase 12/13 - Batch 4: Documents, Context Optimization, Evaluation & Vision (Entries 23-30).
PaddleOCR, MarkItDown, LLMLingua, DSPy, Promptfoo, Inspect AI, Langfuse, Frigate.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cie.capabilities.documents.paddleocr import PaddleOCRAdapter
from cie.capabilities.documents.markitdown import MarkItDownAdapter
from cie.capabilities.documents.llmlingua import LLMLinguaAdapter
from cie.capabilities.documents.dspy import DSPyAdapter, DSPySignature, SignatureField
from cie.capabilities.documents.promptfoo import PromptfooAdapter, PromptfooAssertion
from cie.capabilities.documents.inspect_ai import InspectAIAdapter, BenchmarkSample
from cie.capabilities.documents.langfuse import LangfuseAdapter
from cie.capabilities.vision.frigate import FrigateAdapter


def test_entry23_paddleocr():
    adapter = PaddleOCRAdapter()
    res = adapter.process_image_simulated("data/sample_receipt.png", ["Order #42", "Total: $12.50"])
    assert "Order #42" in res.full_text
    assert len(res.elements) == 2
    assert res.elements[0].confidence >= 0.95


def test_entry24_markitdown():
    adapter = MarkItDownAdapter()
    res = adapter.convert_text_or_html("<h1>Document Title</h1><p>Sample paragraph.</p>")
    assert res.success is True
    assert "Document Title" in res.markdown
    assert "Sample paragraph." in res.markdown


def test_entry25_llmlingua():
    adapter = LLMLinguaAdapter()
    prompt = "This is a very long text with lots of unnecessary words that basically explain a simple concept: ```python\ndef hello():\n    return 'world'\n``` which is really cool."
    res = adapter.compress_prompt(prompt, target_ratio=0.7)
    assert res.compressed_tokens <= res.original_tokens
    # Verify code block was strictly preserved
    assert "def hello():" in res.compressed_text
    assert "return 'world'" in res.compressed_text


def test_entry26_dspy():
    adapter = DSPyAdapter()
    sig = DSPySignature(
        name="SummarizeDoc",
        instructions="Summarize the given document concisely.",
        inputs=[SignatureField(name="document", desc="Input document", prefix="Document:")],
        outputs=[SignatureField(name="summary", desc="Summary output", prefix="Summary:")],
    )
    prompt = adapter.compile_signature_prompt(sig, {"document": "Fastify is fast."})
    assert "Instruction:" in prompt
    assert "Document: Fastify is fast." in prompt
    assert "Summary:" in prompt


def test_entry27_promptfoo():
    adapter = PromptfooAdapter()
    assertions = [
        PromptfooAssertion(type="contains", value="CavrixCode"),
        PromptfooAssertion(type="not-contains", value="forbidden_key"),
        PromptfooAssertion(type="regex", value=r"v\d+\.\d+"),
    ]
    res_pass = adapter.evaluate_response("Welcome to CavrixCode v1.0.0 official build.", assertions)
    assert res_pass.passed is True
    assert res_pass.score == 1.0

    res_fail = adapter.evaluate_response("Welcome to BadCode without version.", assertions)
    assert res_fail.passed is False
    assert "missing" in res_fail.reason or "regex" in res_fail.reason


def test_entry28_inspect_ai():
    adapter = InspectAIAdapter()
    samples = [
        BenchmarkSample(id="s1", input="2 + 2", target="4"),
        BenchmarkSample(id="s2", input="10 * 10", target="100"),
    ]
    def simple_eval_solver(inp: str) -> str:
        if "2 + 2" in inp:
            return "4"
        return "100"

    res = adapter.evaluate_task(samples, simple_eval_solver)
    assert res["total_samples"] == 2
    assert res["mean_accuracy"] == 1.0


def test_entry29_langfuse():
    adapter = LangfuseAdapter()
    trace = adapter.create_trace(trace_id="tr_100", name="ChatSession", user_id="usr_1")
    assert trace.trace_id == "tr_100"

    span = adapter.start_span("tr_100", "sp_1", "ToolExecution", {"tool": "python_ast_validate"})
    assert span is not None
    assert span.status == "running"

    adapter.end_span("tr_100", "sp_1", {"valid": True})
    assert span.status == "completed"
    assert span.end_time is not None


def test_entry30_frigate():
    # Test disabled by default
    adapter_disabled = FrigateAdapter(enabled=False)
    res_disabled = adapter_disabled.handle_webhook_event({"id": "evt_1", "label": "person"})
    assert res_disabled["success"] is False
    assert "disabled" in res_disabled["error"]

    # Test opt-in enabled
    adapter_enabled = FrigateAdapter(enabled=True)
    res_enabled = adapter_enabled.handle_webhook_event({"id": "evt_1", "camera": "front_door", "label": "person", "score": 0.92, "start_time": 1000.0})
    assert res_enabled["success"] is True
    assert res_enabled["label"] == "person"
    events = adapter_enabled.list_recent_events("front_door")
    assert len(events) == 1
