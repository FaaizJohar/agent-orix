"""
Documents, context optimization, and evaluation capabilities (Entries 23-29).
Lazy-loaded to prevent importing heavy dependencies (torch, transformers) on package load.
"""

__all__ = [
    "PaddleOCRAdapter",
    "OCRResult",
    "OCRBoundingBox",
    "MarkItDownAdapter",
    "MarkItDownResult",
    "LLMLinguaAdapter",
    "CompressionResult",
    "DSPyAdapter",
    "DSPySignature",
    "SignatureField",
    "PromptfooAdapter",
    "PromptfooAssertion",
    "EvaluationResult",
    "InspectAIAdapter",
    "BenchmarkSample",
    "InspectAIScore",
    "LangfuseAdapter",
    "LangfuseTrace",
    "LangfuseSpan",
]

_MAP = {
    "PaddleOCRAdapter": ".paddleocr",
    "OCRResult": ".paddleocr",
    "OCRBoundingBox": ".paddleocr",
    "MarkItDownAdapter": ".markitdown",
    "MarkItDownResult": ".markitdown",
    "LLMLinguaAdapter": ".llmlingua",
    "CompressionResult": ".llmlingua",
    "DSPyAdapter": ".dspy",
    "DSPySignature": ".dspy",
    "SignatureField": ".dspy",
    "PromptfooAdapter": ".promptfoo",
    "PromptfooAssertion": ".promptfoo",
    "EvaluationResult": ".promptfoo",
    "InspectAIAdapter": ".inspect_ai",
    "BenchmarkSample": ".inspect_ai",
    "InspectAIScore": ".inspect_ai",
    "LangfuseAdapter": ".langfuse",
    "LangfuseTrace": ".langfuse",
    "LangfuseSpan": ".langfuse",
}


def __getattr__(name: str):
    if name in _MAP:
        import importlib
        mod = importlib.import_module(_MAP[name], package=__name__)
        val = getattr(mod, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
