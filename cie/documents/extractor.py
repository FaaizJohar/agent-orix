"""
Unified Document Extractor for CIE Document Intelligence.
Extracts structured text from PDF, DOCX, XLSX, CSV, Markdown, and TXT.
Enforces PathGuard boundaries, size limits, macro rejection, and encryption handling.
"""

import csv
import io
import os
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

from cie.skills.path_guard import validate_safe_path, PathSecurityError
from cie.documents.ocr import DocumentOcrProvider
from cie.documents.schemas import (
    DocumentChunk,
    DocumentExtractionOptions,
    DocumentExtractionResult,
    DocumentFormat,
)

FORBIDDEN_MACRO_EXTENSIONS = {".docm", ".xlsm", ".pptm", ".dotm", ".xltm", ".potm"}
VBA_PROJECT_SIGNATURE = "vbaproject.bin"


class DocumentExtractor:
    """
    Safely inspects and extracts text from supported document types.
    """

    def __init__(self, options: Optional[DocumentExtractionOptions] = None):
        self.options = options or DocumentExtractionOptions()
        self.ocr_provider = DocumentOcrProvider(enabled=self.options.enable_ocr)

    def detect_format(self, path: Path) -> DocumentFormat:
        """Determines format from file extension and header inspection."""
        ext = path.suffix.lower()
        if ext == ".pdf":
            return DocumentFormat.PDF
        elif ext in (".docx", ".dotx"):
            return DocumentFormat.DOCX
        elif ext in (".xlsx", ".xltx"):
            return DocumentFormat.XLSX
        elif ext == ".csv":
            return DocumentFormat.CSV
        elif ext in (".md", ".markdown"):
            return DocumentFormat.MARKDOWN
        elif ext in (".txt", ".text", ".log"):
            return DocumentFormat.TXT
        return DocumentFormat.UNKNOWN

    def check_macro_safety(self, path: Path) -> None:
        """Rejects files with macro extensions or embedded VBA binary components."""
        ext = path.suffix.lower()
        if ext in FORBIDDEN_MACRO_EXTENSIONS:
            raise PathSecurityError(
                f"File '{path.name}' has a macro-enabled extension '{ext}'. "
                "Execution of macros and active document scripts is strictly prohibited."
            )

        # Inspect ZIP-based archives (.docx, .xlsx) for embedded vbaProject.bin
        if ext in (".docx", ".xlsx", ".zip"):
            try:
                if zipfile.is_zipfile(path):
                    with zipfile.ZipFile(path, "r") as z:
                        for entry in z.namelist():
                            if VBA_PROJECT_SIGNATURE in entry.lower():
                                raise PathSecurityError(
                                    f"File '{path.name}' contains embedded VBA macro component '{entry}'. "
                                    "Processing macro-enabled documents is prohibited."
                                )
            except (zipfile.BadZipFile, OSError):
                pass

    def extract(self, file_path_str: str) -> DocumentExtractionResult:
        """
        Validates, parses, and extracts structured text from the specified document.
        """
        try:
            abs_path = validate_safe_path(file_path_str, must_exist=True, must_be_file=True)
        except (PathSecurityError, FileNotFoundError) as pse:
            return DocumentExtractionResult(
                source_path=file_path_str,
                format=DocumentFormat.UNKNOWN,
                error=f"Security/Path error: {str(pse)}",
            )
        except Exception as e:
            return DocumentExtractionResult(
                source_path=file_path_str,
                format=DocumentFormat.UNKNOWN,
                error=f"Cannot access file: {str(e)}",
            )

        # 1. Macro safety check
        try:
            self.check_macro_safety(abs_path)
        except PathSecurityError as pse:
            return DocumentExtractionResult(
                source_path=str(abs_path),
                format=self.detect_format(abs_path),
                error=str(pse),
            )

        # 2. File size & emptiness check
        try:
            st_size = abs_path.stat().st_size
            if st_size == 0:
                return DocumentExtractionResult(
                    source_path=str(abs_path),
                    format=self.detect_format(abs_path),
                    error=f"Document file is empty (0 bytes): {abs_path.name}",
                )
            if st_size > self.options.max_file_bytes:
                return DocumentExtractionResult(
                    source_path=str(abs_path),
                    format=self.detect_format(abs_path),
                    error=(
                        f"Document size ({st_size} bytes) exceeds maximum allowable limit "
                        f"of {self.options.max_file_bytes} bytes (10MB)."
                    ),
                )
        except OSError as e:
            return DocumentExtractionResult(
                source_path=str(abs_path),
                format=self.detect_format(abs_path),
                error=f"Cannot stat file: {str(e)}",
            )

        fmt = self.detect_format(abs_path)
        if fmt == DocumentFormat.UNKNOWN:
            return DocumentExtractionResult(
                source_path=str(abs_path),
                format=DocumentFormat.UNKNOWN,
                error=f"Unsupported document format '{abs_path.suffix}'. Supported formats: PDF, DOCX, XLSX, CSV, Markdown, TXT.",
            )

        # 3. Format-specific extraction
        try:
            if fmt == DocumentFormat.PDF:
                return self._extract_pdf(abs_path)
            elif fmt == DocumentFormat.DOCX:
                return self._extract_docx(abs_path)
            elif fmt == DocumentFormat.XLSX:
                return self._extract_xlsx(abs_path)
            elif fmt == DocumentFormat.CSV:
                return self._extract_csv(abs_path)
            elif fmt == DocumentFormat.MARKDOWN:
                return self._extract_markdown(abs_path)
            elif fmt == DocumentFormat.TXT:
                return self._extract_txt(abs_path)
        except Exception as e:
            return DocumentExtractionResult(
                source_path=str(abs_path),
                format=fmt,
                error=f"Document parsing error in {fmt.value.upper()}: {str(e)}",
            )

        return DocumentExtractionResult(
            source_path=str(abs_path),
            format=fmt,
            error="Extraction not handled.",
        )

    def _extract_pdf(self, path: Path) -> DocumentExtractionResult:
        import pypdf

        try:
            reader = pypdf.PdfReader(str(path))
        except Exception as e:
            return DocumentExtractionResult(
                source_path=str(path),
                format=DocumentFormat.PDF,
                error=f"Malformed or corrupted PDF file: {str(e)}",
            )

        if reader.is_encrypted:
            return DocumentExtractionResult(
                source_path=str(path),
                format=DocumentFormat.PDF,
                is_encrypted=True,
                error="PDF is encrypted or password-protected. Unencrypted documents are required.",
            )

        total_pages = len(reader.pages)
        pages_to_process = min(total_pages, self.options.max_pages)
        chunks: List[DocumentChunk] = []
        full_text_parts: List[str] = []
        total_chars = 0
        is_scanned = True

        for p_idx in range(pages_to_process):
            page_num = p_idx + 1
            try:
                page = reader.pages[p_idx]
                page_text = page.extract_text() or ""
            except Exception as e:
                page_text = f"[Error reading page {page_num}: {str(e)}]"

            page_stripped = page_text.strip()
            if page_stripped:
                is_scanned = False
                header = f"[Page {page_num}]"
                full_text_parts.append(f"{header}\n{page_stripped}\n")
                total_chars += len(page_stripped)

                # Create structured page chunk
                chunk = DocumentChunk(
                    chunk_id=f"page_{page_num}",
                    document_path=str(path),
                    chunk_index=p_idx,
                    page_number=page_num,
                    section_title=f"Page {page_num}",
                    content=page_stripped,
                    token_estimate=len(page_stripped) // 4,
                )
                chunks.append(chunk)

            if total_chars >= self.options.max_total_chars:
                break

        # Handle scanned PDFs where text extraction returned empty
        ocr_applied = False
        if is_scanned and total_pages > 0:
            if not self.options.enable_ocr:
                return DocumentExtractionResult(
                    source_path=str(path),
                    format=DocumentFormat.PDF,
                    total_pages=total_pages,
                    total_characters=0,
                    is_scanned=True,
                    ocr_applied=False,
                    error=(
                        "Document appears to be a scanned image-based PDF with no digital text layer. "
                        "OCR is disabled by default to conserve memory. Enable OCR via configuration if needed."
                    ),
                )
            else:
                # OCR branch
                ocr_text, ocr_applied, ocr_err = self.ocr_provider.process_image(b"")
                if ocr_err:
                    return DocumentExtractionResult(
                        source_path=str(path),
                        format=DocumentFormat.PDF,
                        total_pages=total_pages,
                        is_scanned=True,
                        ocr_applied=False,
                        error=ocr_err,
                    )

        full_text = "\n".join(full_text_parts)

        return DocumentExtractionResult(
            source_path=str(path),
            format=DocumentFormat.PDF,
            total_pages=total_pages,
            total_characters=len(full_text),
            full_text=full_text,
            chunks=chunks,
            is_scanned=is_scanned,
            ocr_applied=ocr_applied,
            error=None,
        )

    def _extract_docx(self, path: Path) -> DocumentExtractionResult:
        import docx

        try:
            doc = docx.Document(str(path))
        except Exception as e:
            return DocumentExtractionResult(
                source_path=str(path),
                format=DocumentFormat.DOCX,
                error=f"Malformed or corrupted DOCX file: {str(e)}",
            )

        chunks: List[DocumentChunk] = []
        full_text_parts: List[str] = []
        current_section = "Introduction"
        current_section_lines: List[str] = []
        chunk_idx = 0

        def flush_section():
            nonlocal chunk_idx
            if current_section_lines:
                sec_text = "\n".join(current_section_lines).strip()
                if sec_text:
                    full_text_parts.append(f"[Section: {current_section}]\n{sec_text}\n")
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"sec_{chunk_idx}",
                            document_path=str(path),
                            chunk_index=chunk_idx,
                            section_title=current_section,
                            content=sec_text,
                            token_estimate=len(sec_text) // 4,
                        )
                    )
                    chunk_idx += 1
                current_section_lines.clear()

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            # Detect headings
            if p.style and p.style.name and p.style.name.startswith("Heading"):
                flush_section()
                current_section = text
            else:
                current_section_lines.append(text)

        # Also extract structured tables
        for t_idx, table in enumerate(doc.tables, start=1):
            flush_section()
            current_section = f"Table {t_idx}"
            table_lines: List[str] = []
            for r_idx, row in enumerate(table.rows, start=1):
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                table_lines.append(f"[Row {r_idx}] " + " | ".join(row_cells))
            current_section_lines.extend(table_lines)
            flush_section()

        flush_section()

        full_text = "\n".join(full_text_parts)
        return DocumentExtractionResult(
            source_path=str(path),
            format=DocumentFormat.DOCX,
            total_characters=len(full_text),
            full_text=full_text,
            chunks=chunks,
            error=None,
        )

    def _extract_xlsx(self, path: Path) -> DocumentExtractionResult:
        import openpyxl

        try:
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        except Exception as e:
            return DocumentExtractionResult(
                source_path=str(path),
                format=DocumentFormat.XLSX,
                error=f"Malformed or corrupted XLSX spreadsheet: {str(e)}",
            )

        sheet_names = wb.sheetnames
        sheets_to_process = sheet_names[: self.options.max_sheets]
        chunks: List[DocumentChunk] = []
        full_text_parts: List[str] = []
        chunk_idx = 0

        for s_name in sheets_to_process:
            ws = wb[s_name]
            sheet_lines: List[str] = []
            row_count = 0

            for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                if row_count >= self.options.max_rows_per_sheet:
                    sheet_lines.append(f"... [Truncated at {self.options.max_rows_per_sheet} rows]")
                    break

                row_vals = [str(v).strip() if v is not None else "" for v in row]
                if any(row_vals):  # skip completely blank rows
                    sheet_lines.append(f"[Row {r_idx}] " + " | ".join(row_vals))
                    row_count += 1

            if sheet_lines:
                sheet_content = "\n".join(sheet_lines)
                header = f"[Sheet: {s_name}]"
                full_text_parts.append(f"{header}\n{sheet_content}\n")
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"sheet_{chunk_idx}",
                        document_path=str(path),
                        chunk_index=chunk_idx,
                        sheet_name=s_name,
                        row_range=f"1-{row_count}",
                        section_title=f"Sheet: {s_name}",
                        content=sheet_content,
                        token_estimate=len(sheet_content) // 4,
                    )
                )
                chunk_idx += 1

        wb.close()
        full_text = "\n".join(full_text_parts)

        return DocumentExtractionResult(
            source_path=str(path),
            format=DocumentFormat.XLSX,
            total_sheets=len(sheet_names),
            total_characters=len(full_text),
            full_text=full_text,
            chunks=chunks,
            error=None,
        )

    def _extract_csv(self, path: Path) -> DocumentExtractionResult:
        lines: List[str] = []
        row_count = 0
        encodings = ("utf-8", "utf-8-sig", "cp1252", "latin-1")
        csv_file = None

        for enc in encodings:
            try:
                csv_file = open(path, "r", encoding=enc, errors="replace")
                reader = csv.reader(csv_file)
                for r_idx, row in enumerate(reader, start=1):
                    if row_count >= self.options.max_rows_per_sheet:
                        lines.append(f"... [Truncated at {self.options.max_rows_per_sheet} rows]")
                        break
                    row_vals = [c.strip() for c in row]
                    if any(row_vals):
                        lines.append(f"[Row {r_idx}] " + " | ".join(row_vals))
                        row_count += 1
                break
            except Exception:
                continue
            finally:
                if csv_file:
                    csv_file.close()

        if not lines:
            return DocumentExtractionResult(
                source_path=str(path),
                format=DocumentFormat.CSV,
                error="Unable to read or decode CSV content.",
            )

        content = "\n".join(lines)
        chunk = DocumentChunk(
            chunk_id="csv_0",
            document_path=str(path),
            chunk_index=0,
            section_title="CSV Data Table",
            row_range=f"1-{row_count}",
            content=content,
            token_estimate=len(content) // 4,
        )

        return DocumentExtractionResult(
            source_path=str(path),
            format=DocumentFormat.CSV,
            total_characters=len(content),
            full_text=content,
            chunks=[chunk],
            error=None,
        )

    def _extract_markdown(self, path: Path) -> DocumentExtractionResult:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
        except Exception as e:
            return DocumentExtractionResult(
                source_path=str(path),
                format=DocumentFormat.MARKDOWN,
                error=f"Failed to read markdown file: {str(e)}",
            )

        chunks: List[DocumentChunk] = []
        sections = raw_text.split("\n#")
        chunk_idx = 0

        for idx, sec in enumerate(sections):
            text = sec.strip()
            if not text:
                continue

            sec_text = text if idx == 0 and not text.startswith("#") else f"#{text}"
            first_line = sec_text.split("\n")[0].lstrip("#").strip()
            title = first_line if first_line else f"Section {chunk_idx + 1}"

            chunks.append(
                DocumentChunk(
                    chunk_id=f"md_{chunk_idx}",
                    document_path=str(path),
                    chunk_index=chunk_idx,
                    section_title=title,
                    content=sec_text,
                    token_estimate=len(sec_text) // 4,
                )
            )
            chunk_idx += 1

        return DocumentExtractionResult(
            source_path=str(path),
            format=DocumentFormat.MARKDOWN,
            total_characters=len(raw_text),
            full_text=raw_text,
            chunks=chunks,
            error=None,
        )

    def _extract_txt(self, path: Path) -> DocumentExtractionResult:
        raw_text = ""
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(path, "r", encoding=enc) as f:
                    raw_text = f.read()
                break
            except UnicodeDecodeError:
                continue

        if not raw_text:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    raw_text = f.read()
            except Exception as e:
                return DocumentExtractionResult(
                    source_path=str(path),
                    format=DocumentFormat.TXT,
                    error=f"Cannot read plaintext file: {str(e)}",
                )

        # Chunk by paragraph
        paras = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        chunks: List[DocumentChunk] = []
        current_p_chunk: List[str] = []
        current_len = 0
        chunk_idx = 0

        for p in paras:
            current_p_chunk.append(p)
            current_len += len(p)
            if current_len >= 1200:
                joined = "\n\n".join(current_p_chunk)
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"txt_{chunk_idx}",
                        document_path=str(path),
                        chunk_index=chunk_idx,
                        section_title=f"Paragraph {chunk_idx + 1}",
                        content=joined,
                        token_estimate=len(joined) // 4,
                    )
                )
                chunk_idx += 1
                current_p_chunk.clear()
                current_len = 0

        if current_p_chunk:
            joined = "\n\n".join(current_p_chunk)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"txt_{chunk_idx}",
                    document_path=str(path),
                    chunk_index=chunk_idx,
                    section_title=f"Paragraph {chunk_idx + 1}",
                    content=joined,
                    token_estimate=len(joined) // 4,
                )
            )

        return DocumentExtractionResult(
            source_path=str(path),
            format=DocumentFormat.TXT,
            total_characters=len(raw_text),
            full_text=raw_text,
            chunks=chunks,
            error=None,
        )
