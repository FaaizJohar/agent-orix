"""
Document Ingestion Pipeline for CIE Knowledge Subsystem.
Enforces file format restrictions, path traversal guards, secret file exclusion, and chunking.
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cie.context import estimate_tokens
from cie.knowledge.store import KnowledgeStore

ALLOWED_EXTENSIONS = {".md", ".txt"}
DISALLOWED_NAMES = {
    ".env", ".git", ".gitignore", "id_rsa", "id_ecdsa", "id_ed25519",
    "credentials", "secrets", "passwords", "node_modules", "venv", "__pycache__"
}
MAX_FILE_BYTES = 512_000  # 500 KB limit per document
CHUNK_TARGET_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150


class IngestionSecurityError(Exception):
    pass


class IngestionSizeLimitError(Exception):
    pass


class DocumentIngester:
    def __init__(self, store: Optional[KnowledgeStore] = None):
        self.store = store or KnowledgeStore()

    def validate_file_path(self, path: Path) -> Path:
        """
        Validates path existence, format extension, and secret file exclusion.
        """
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")

        if not resolved.is_file():
            raise IngestionSecurityError(f"Path is not a regular file: {resolved}")

        # Check extension
        if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise IngestionSecurityError(
                f"Unsupported file format '{resolved.suffix}'. Only .md and .txt are permitted."
            )

        # Check secret or blacklisted filenames
        name_lower = resolved.name.lower()
        if any(bad in name_lower for bad in DISALLOWED_NAMES):
            raise IngestionSecurityError(
                f"File '{resolved.name}' matches disallowed secret or system patterns."
            )

        # Check file size
        size_bytes = resolved.stat().st_size
        if size_bytes > MAX_FILE_BYTES:
            raise IngestionSizeLimitError(
                f"File size ({size_bytes} bytes) exceeds maximum limit of {MAX_FILE_BYTES} bytes."
            )

        return resolved

    def read_file_safe(self, path: Path) -> str:
        """
        Safely reads file with encoding fallback.
        """
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Unable to decode text for file {path} with supported encodings.")

    def chunk_text(self, text: str, title: str) -> List[Tuple[str, str]]:
        """
        Splits text into logical, paragraph-bounded chunks.
        Returns: List of (chunk_title, chunk_content)
        """
        paragraphs = text.split("\n\n")
        chunks: List[Tuple[str, str]] = []
        current_chunk: List[str] = []
        current_len = 0
        current_section = title

        for p in paragraphs:
            stripped = p.strip()
            if not stripped:
                continue

            # Detect markdown header to update section title
            if stripped.startswith("#"):
                current_section = stripped.split("\n")[0].lstrip("#").strip()

            p_len = len(stripped)
            if current_len + p_len > CHUNK_TARGET_CHARS and current_chunk:
                chunk_str = "\n\n".join(current_chunk)
                chunks.append((current_section, chunk_str))
                # Keep last paragraph for overlap if reasonable
                if len(current_chunk[-1]) <= CHUNK_OVERLAP_CHARS:
                    current_chunk = [current_chunk[-1], stripped]
                    current_len = len(current_chunk[0]) + p_len
                else:
                    current_chunk = [stripped]
                    current_len = p_len
            else:
                current_chunk.append(stripped)
                current_len += p_len

        if current_chunk:
            chunk_str = "\n\n".join(current_chunk)
            chunks.append((current_section, chunk_str))

        return chunks

    def ingest_file(
        self,
        path: Path,
        collection: str = "default",
        metadata: Optional[Dict] = None,
    ) -> Tuple[int, int, bool]:
        """
        Ingests a single validated document into SQLite and FTS5.
        Returns: (doc_id, chunk_count, was_reindexed)
        """
        validated_path = self.validate_file_path(path)
        content = self.read_file_safe(validated_path)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        size_bytes = validated_path.stat().st_size

        # Extract title from first markdown header or filename
        title = validated_path.stem
        for line in content.splitlines()[:5]:
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break

        doc_id, was_new_or_modified = self.store.upsert_document(
            collection=collection,
            source_path=str(validated_path),
            title=title,
            content_hash=content_hash,
            size_bytes=size_bytes,
            metadata=metadata,
        )

        if not was_new_or_modified:
            # Document unchanged, return existing count
            return doc_id, 0, False

        # Split into chunks and index into FTS5
        chunks = self.chunk_text(content, title)
        for idx, (chunk_title, chunk_content) in enumerate(chunks):
            chunk_identifier = f"Doc_{doc_id}_Chunk_{idx}"
            tokens = estimate_tokens(chunk_content)
            self.store.insert_chunk(
                document_id=doc_id,
                chunk_index=idx,
                chunk_identifier=chunk_identifier,
                title=f"{title} - {chunk_title}",
                content=chunk_content,
                token_estimate=tokens,
            )

        return doc_id, len(chunks), True

    def ingest_directory(
        self,
        dir_path: Path,
        collection: str = "default",
    ) -> Dict[str, Any]:
        """
        Ingests all allowed files in a directory non-recursively.
        """
        if not dir_path.exists() or not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        ingested = 0
        skipped = 0
        errors: List[str] = []

        for p in dir_path.glob("*"):
            if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS:
                try:
                    _, chunk_count, reindexed = self.ingest_file(p, collection=collection)
                    if reindexed:
                        ingested += 1
                    else:
                        skipped += 1
                except Exception as e:
                    errors.append(f"{p.name}: {str(e)}")

        return {
            "collection": collection,
            "directory": str(dir_path),
            "ingested_or_updated": ingested,
            "unchanged_skipped": skipped,
            "errors": errors,
        }
