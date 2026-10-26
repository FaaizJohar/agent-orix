"""
Data schemas and models for Document Intelligence & Grounded Question Answering.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    MARKDOWN = "markdown"
    TXT = "txt"
    UNKNOWN = "unknown"


class DocumentExtractionOptions(BaseModel):
    max_file_bytes: int = Field(default=10_485_760, description="Max allowed file size (10 MB)")
    max_pages: int = Field(default=50, ge=1, le=200, description="Max pages to extract from PDF")
    max_sheets: int = Field(default=10, ge=1, le=50, description="Max sheets to extract from spreadsheet")
    max_rows_per_sheet: int = Field(default=300, ge=1, le=1000, description="Max rows per sheet or CSV")
    enable_ocr: bool = Field(default=False, description="Enable OCR for scanned documents (default False to conserve RAM)")
    max_total_chars: int = Field(default=200_000, description="Max total characters extracted across document")


class DocumentChunk(BaseModel):
    chunk_id: str
    document_path: str
    chunk_index: int
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    sheet_name: Optional[str] = None
    row_range: Optional[str] = None
    content: str
    token_estimate: int = 0


class DocumentExtractionResult(BaseModel):
    source_path: str
    format: DocumentFormat
    total_pages: Optional[int] = None
    total_sheets: Optional[int] = None
    total_characters: int = 0
    full_text: str = ""
    chunks: List[DocumentChunk] = Field(default_factory=list)
    is_encrypted: bool = False
    is_scanned: bool = False
    ocr_applied: bool = False
    error: Optional[str] = None


class DocumentExtractTextInput(BaseModel):
    file_path: str = Field(..., description="Path to local document file within approved workspace")
    max_pages: int = Field(default=50, ge=1, le=200, description="Max pages for PDF")
    max_sheets: int = Field(default=10, ge=1, le=50, description="Max sheets for spreadsheets")
    max_rows: int = Field(default=300, ge=1, le=1000, description="Max rows for tables/CSV")
    enable_ocr: bool = Field(default=False, description="Optional OCR toggle (default False)")


class DocumentExtractTextOutput(BaseModel):
    file_path: str
    format: str
    total_pages: Optional[int] = None
    total_sheets: Optional[int] = None
    total_characters: int = 0
    content_preview: str = ""
    is_encrypted: bool = False
    is_scanned: bool = False
    ocr_applied: bool = False
    error: Optional[str] = None


class DocumentQAInput(BaseModel):
    file_path: str = Field(..., description="Path to document file to query")
    question: str = Field(..., min_length=2, max_length=2000, description="Question about the document contents")
    max_chunks: int = Field(default=4, ge=1, le=10, description="Max relevant chunks to retrieve")


class DocumentQAResult(BaseModel):
    file_path: str
    question: str
    answer: str
    citations: List[str] = Field(default_factory=list)
    evidence_chunks: List[DocumentChunk] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    execution_time_ms: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class DocumentQAOutput(BaseModel):
    file_path: str
    question: str
    answer: str
    citations: List[str] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    chunks_retrieved: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
