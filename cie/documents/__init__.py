"""
Document Intelligence Subsystem for CIE.
Provides safe, structured text extraction, OCR toggle, chunking,
and grounded question answering across PDF, DOCX, XLSX, CSV, Markdown, and TXT.
"""

from cie.documents.schemas import (
    DocumentFormat,
    DocumentExtractionOptions,
    DocumentChunk,
    DocumentExtractionResult,
    DocumentQAResult,
    DocumentExtractTextInput,
    DocumentExtractTextOutput,
    DocumentQAInput,
    DocumentQAOutput,
)
from cie.documents.extractor import DocumentExtractor
from cie.documents.retriever import DocumentRetriever
from cie.documents.qa_engine import DocumentQAEngine

__all__ = [
    "DocumentFormat",
    "DocumentExtractionOptions",
    "DocumentChunk",
    "DocumentExtractionResult",
    "DocumentQAResult",
    "DocumentExtractTextInput",
    "DocumentExtractTextOutput",
    "DocumentQAInput",
    "DocumentQAOutput",
    "DocumentExtractor",
    "DocumentRetriever",
    "DocumentQAEngine",
]
