"""
Tests for DocumentIngester security, format filtering, and chunking.
"""

import pytest
from pathlib import Path
from cie.knowledge.ingester import (
    DocumentIngester,
    IngestionSecurityError,
    IngestionSizeLimitError,
)
from cie.knowledge.store import KnowledgeStore


@pytest.fixture
def ingester(tmp_path):
    db_file = tmp_path / "test_ingest.db"
    store = KnowledgeStore(db_path=db_file)
    return DocumentIngester(store=store)


def test_reject_unsupported_extensions(ingester, tmp_path):
    bad_file = tmp_path / "script.py"
    bad_file.write_text("print('hello')", encoding="utf-8")
    with pytest.raises(IngestionSecurityError) as exc:
        ingester.validate_file_path(bad_file)
    assert "Unsupported file format" in str(exc.value)


def test_reject_secret_and_env_files(ingester, tmp_path):
    secret_files = [".env.txt", "credentials.txt", "id_rsa.txt"]
    for fname in secret_files:
        f = tmp_path / fname
        f.write_text("secret_data=123", encoding="utf-8")
        with pytest.raises(IngestionSecurityError) as exc:
            ingester.validate_file_path(f)
        assert "disallowed secret" in str(exc.value)


def test_reject_oversized_file(ingester, tmp_path):
    big_file = tmp_path / "big_doc.txt"
    big_file.write_text("A" * 600_000, encoding="utf-8")  # > 500 KB limit
    with pytest.raises(IngestionSizeLimitError):
        ingester.validate_file_path(big_file)


def test_successful_file_ingestion(ingester, tmp_path):
    doc_file = tmp_path / "sample.md"
    doc_file.write_text(
        "# Sample Document\n\nThis is paragraph one.\n\n## Section Two\n\nThis is paragraph two.",
        encoding="utf-8",
    )
    doc_id, chunk_count, reindexed = ingester.ingest_file(doc_file, collection="test_col")
    assert doc_id >= 1
    assert chunk_count >= 1
    assert reindexed is True
