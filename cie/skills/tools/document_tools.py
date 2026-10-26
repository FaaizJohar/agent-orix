"""
Developer & Agent Tools for Document Intelligence.
Integrates safe document extraction and grounded document question answering into the Skills Registry.
"""

import json
from typing import Any, Dict, List, Optional

from cie.documents.extractor import DocumentExtractor
from cie.documents.qa_engine import DocumentQAEngine
from cie.documents.schemas import (
    DocumentExtractionOptions,
    DocumentExtractTextInput,
    DocumentExtractTextOutput,
    DocumentQAInput,
    DocumentQAOutput,
)
from pydantic import BaseModel, Field


class MarkItDownConvertInput(BaseModel):
    file_path: Optional[str] = Field(None, description="Path to document file on disk (PDF, DOCX, XLSX, HTML, etc.)")
    content: Optional[str] = Field(None, description="Raw content string (e.g. HTML or text) if file_path is omitted")
    file_extension: str = Field(".html", description="File extension when providing raw content")


class MarkItDownConvertOutput(BaseModel):
    markdown: str
    source: str
    file_type: str
    success: bool
    upstream_used: bool
    error: Optional[str] = None


def markitdown_convert(
    file_path: Optional[str] = None,
    content: Optional[str] = None,
    file_extension: str = ".html",
) -> MarkItDownConvertOutput:
    """
    Converts documents or HTML into clean, readable Markdown using Microsoft's MarkItDown library.
    """
    from cie.capabilities.documents.markitdown import MarkItDownAdapter
    adapter = MarkItDownAdapter()

    if file_path:
        res = adapter.convert_file(file_path)
        return MarkItDownConvertOutput(
            markdown=res.markdown,
            source=res.source_file,
            file_type=res.file_type,
            success=res.success,
            upstream_used=adapter.upstream_active,
            error=res.error,
        )
    elif content is not None:
        res = adapter.convert_text_or_html(content, extension=file_extension)
        return MarkItDownConvertOutput(
            markdown=res.markdown,
            source=res.source_file,
            file_type=res.file_type,
            success=res.success,
            upstream_used=adapter.upstream_active,
            error=res.error,
        )
    else:
        return MarkItDownConvertOutput(
            markdown="",
            source="none",
            file_type=file_extension,
            success=False,
            upstream_used=adapter.upstream_active,
            error="Either file_path or content must be provided.",
        )


def document_extract_text(
    file_path: str,
    max_pages: int = 50,
    max_sheets: int = 10,
    max_rows: int = 300,
    enable_ocr: bool = False,
) -> DocumentExtractTextOutput:
    """
    Extracts structured plaintext and hierarchy from PDF, Word, Excel, CSV, Markdown, or text files.
    """
    options = DocumentExtractionOptions(
        max_pages=max_pages,
        max_sheets=max_sheets,
        max_rows_per_sheet=max_rows,
        enable_ocr=enable_ocr,
    )
    extractor = DocumentExtractor(options=options)
    res = extractor.extract(file_path)

    preview = res.full_text[:500] if res.full_text else ""
    if len(res.full_text) > 500:
        preview += "... [truncated preview]"

    return DocumentExtractTextOutput(
        file_path=res.source_path,
        format=res.format.value,
        total_pages=res.total_pages,
        total_sheets=res.total_sheets,
        total_characters=res.total_characters,
        content_preview=preview,
        is_encrypted=res.is_encrypted,
        is_scanned=res.is_scanned,
        ocr_applied=res.ocr_applied,
        error=res.error,
    )


async def document_qa(
    file_path: str,
    question: str,
    max_chunks: int = 4,
) -> DocumentQAOutput:
    """
    Answers user questions grounded directly in a local document using FTS5 retrieval and verified citations.
    """
    engine = DocumentQAEngine()
    result = await engine.answer_question(
        file_path=file_path,
        question=question,
        max_chunks=max_chunks,
    )

    return DocumentQAOutput(
        file_path=result.file_path,
        question=result.question,
        answer=result.answer,
        citations=result.citations,
        has_sufficient_evidence=result.has_sufficient_evidence,
        chunks_retrieved=len(result.evidence_chunks),
        duration_ms=result.execution_time_ms,
        error=result.error,
    )


class DSPyCompileSignatureInput(BaseModel):
    name: str = Field(..., description="Signature name, e.g. 'SummarizeDoc' or 'GenerateCode'")
    instructions: str = Field(..., description="High-level task instructions")
    inputs: List[Dict[str, str]] = Field(..., description="List of input field definitions with 'name', 'desc', and 'prefix'")
    outputs: List[Dict[str, str]] = Field(..., description="List of output field definitions with 'name', 'desc', and 'prefix'")
    input_values: Dict[str, Any] = Field(default_factory=dict, description="Values for the input fields")


class DSPyCompileSignatureOutput(BaseModel):
    signature_name: str
    compiled_prompt: str
    upstream_used: bool
    field_count: int


def dspy_compile_signature(
    name: str,
    instructions: str,
    inputs: List[Dict[str, str]],
    outputs: List[Dict[str, str]],
    input_values: Dict[str, Any],
) -> DSPyCompileSignatureOutput:
    """
    Compiles declarative DSPy signatures into structured teleprompter prompts
    using upstream stanfordnlp/dspy declarative primitives.
    """
    from cie.capabilities.documents.dspy import DSPyAdapter, DSPySignature, SignatureField
    adapter = DSPyAdapter()

    in_fields = [
        SignatureField(
            name=f.get("name", "input"),
            desc=f.get("desc", ""),
            prefix=f.get("prefix", f"{f.get('name', 'input')}:"),
        )
        for f in inputs
    ]
    out_fields = [
        SignatureField(
            name=f.get("name", "output"),
            desc=f.get("desc", ""),
            prefix=f.get("prefix", f"{f.get('name', 'output')}:"),
        )
        for f in outputs
    ]
    sig = DSPySignature(
        name=name,
        instructions=instructions,
        inputs=in_fields,
        outputs=out_fields,
    )
    prompt = adapter.compile_signature_prompt(sig, input_values)
    return DSPyCompileSignatureOutput(
        signature_name=name,
        compiled_prompt=prompt,
        upstream_used=adapter.upstream_active,
        field_count=len(in_fields) + len(out_fields),
    )


class InspectAIEvalInput(BaseModel):
    task_name: str = Field("eval_task", description="Evaluation benchmark task identifier")
    samples: List[Dict[str, str]] = Field(..., description="List of evaluation samples with 'id', 'input', 'target'")
    predictions: Optional[Dict[str, str]] = Field(default=None, description="Optional map of sample id to predicted output string")


class InspectAIEvalOutput(BaseModel):
    task_name: str
    total_samples: int
    mean_accuracy: float
    scores: List[Dict[str, Any]]
    upstream_used: bool


def inspect_ai_eval(
    task_name: str,
    samples: List[Dict[str, str]],
    predictions: Optional[Dict[str, str]] = None,
) -> InspectAIEvalOutput:
    """
    Evaluates benchmark samples and calculates accuracy metrics conforming to UK AISI Inspect AI.
    """
    from cie.capabilities.documents.inspect_ai import InspectAIAdapter, BenchmarkSample
    adapter = InspectAIAdapter()

    preds = predictions or {}
    bench_samples = [
        BenchmarkSample(
            id=s.get("id", f"s_{idx}"),
            input=s.get("input", ""),
            target=s.get("target", ""),
        )
        for idx, s in enumerate(samples)
    ]

    solver = lambda inp: preds.get(inp, preds.get(next((s.id for s in bench_samples if s.input == inp), ""), ""))
    res = adapter.evaluate_task(bench_samples, solver)

    return InspectAIEvalOutput(
        task_name=task_name,
        total_samples=res["total_samples"],
        mean_accuracy=res["mean_accuracy"],
        scores=res["scores"],
        upstream_used=adapter.upstream_active,
    )


# =============================================================================
# Tool 43: hermes_format_tool_call (NousResearch Hermes Function Calling Protocol)
# =============================================================================

class HermesFormatToolCallInput(BaseModel):
    tool_name: str = Field(..., description="Name of the function/tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool invocation parameters")
    raw_response: Optional[str] = Field(None, description="Optional raw model output to parse for <tool_call> tags")


class HermesFormatToolCallOutput(BaseModel):
    formatted_call: str
    parsed_calls: List[Dict[str, Any]]
    upstream_used: bool


def hermes_format_tool_call(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    raw_response: Optional[str] = None,
) -> HermesFormatToolCallOutput:
    """
    Formats or parses structured tool calls using upstream NousResearch Hermes primitives.
    """
    from cie.capabilities.agent.hermes import HermesAgentAdapter, HermesToolCall
    adapter = HermesAgentAdapter()

    args = arguments or {}
    formatted = f"<tool_call>\n{{\"name\": \"{tool_name}\", \"arguments\": {json.dumps(args)}}}\n</tool_call>"

    parsed_list = []
    if raw_response:
        calls = adapter.parse_tool_calls(raw_response)
        parsed_list = [{"name": c.name, "arguments": c.arguments} for c in calls]
    else:
        calls = adapter.parse_tool_calls(formatted)
        parsed_list = [{"name": c.name, "arguments": c.arguments} for c in calls]

    return HermesFormatToolCallOutput(
        formatted_call=formatted,
        parsed_calls=parsed_list,
        upstream_used=adapter.upstream_active,
    )


# =============================================================================
# Tool 44: lightrag_query_graph (HKUDS LightRAG Dual-Level Graph Retrieval)
# =============================================================================

class LightRAGQueryInput(BaseModel):
    query: str = Field(..., description="Query for graph-based dual-level retrieval")
    mode: str = Field("dual", description="Query mode: 'dual', 'low_level', or 'high_level'")
    entities: Optional[List[Dict[str, str]]] = Field(None, description="Optional entities to index before querying")
    themes: Optional[List[Dict[str, Any]]] = Field(None, description="Optional high-level community themes to index")


class LightRAGQueryOutput(BaseModel):
    query: str
    low_level_entities: List[Dict[str, Any]]
    high_level_themes: List[Dict[str, Any]]
    upstream_used: bool


def lightrag_query_graph(
    query: str,
    mode: str = "dual",
    entities: Optional[List[Dict[str, str]]] = None,
    themes: Optional[List[Dict[str, Any]]] = None,
) -> LightRAGQueryOutput:
    """
    Executes dual-level graph retrieval across low-level entities and high-level themes
    using HKUDS LightRAG upstream primitives.
    """
    from cie.capabilities.knowledge.lightrag import LightRAGAdapter, EntityNode, CommunitySummary
    adapter = LightRAGAdapter()

    if entities:
        for ent in entities:
            adapter.add_entity(EntityNode(
                name=ent.get("name", "unknown"),
                entity_type=ent.get("entity_type", "entity"),
                description=ent.get("description", ""),
            ))

    if themes:
        for thm in themes:
            adapter.add_community(CommunitySummary(
                community_id=thm.get("community_id", "c0"),
                theme=thm.get("theme", "general"),
                entities=thm.get("entities", []),
                summary=thm.get("summary", ""),
            ))

    res = adapter.dual_level_query(query)

    return LightRAGQueryOutput(
        query=query,
        low_level_entities=res["low_level_entities"],
        high_level_themes=res["high_level_themes"],
        upstream_used=adapter.upstream_active,
    )


