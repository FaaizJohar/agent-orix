"""
Tests for KnowledgeStore SQLite FTS5 database and memory CRUD operations.
"""

import pytest
from pathlib import Path
from cie.knowledge.store import KnowledgeStore


@pytest.fixture
def temp_store(tmp_path):
    db_file = tmp_path / "test_knowledge.db"
    return KnowledgeStore(db_path=db_file)


def test_schema_creation_and_migration(temp_store):
    with temp_store._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations;")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 1

        # Verify tables exist
        tables = [
            r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        ]
        assert "documents" in tables
        assert "document_chunks" in tables
        assert "document_chunks_fts" in tables
        assert "memories" in tables
        assert "retrieval_audits" in tables


def test_upsert_document_and_reindex(temp_store):
    doc_id1, reindexed1 = temp_store.upsert_document(
        collection="test",
        source_path="/path/test.md",
        title="Test Doc",
        content_hash="hash_v1",
        size_bytes=100,
    )
    assert reindexed1 is True

    # Re-upsert with same content hash -> should NOT reindex
    doc_id2, reindexed2 = temp_store.upsert_document(
        collection="test",
        source_path="/path/test.md",
        title="Test Doc",
        content_hash="hash_v1",
        size_bytes=100,
    )
    assert doc_id1 == doc_id2
    assert reindexed2 is False

    # Update with new content hash -> should reindex
    doc_id3, reindexed3 = temp_store.upsert_document(
        collection="test",
        source_path="/path/test.md",
        title="Test Doc v2",
        content_hash="hash_v2",
        size_bytes=120,
    )
    assert doc_id1 == doc_id3
    assert reindexed3 is True


def test_fts5_indexing_and_search(temp_store):
    doc_id, _ = temp_store.upsert_document(
        collection="cavrix",
        source_path="/cavrix/info.md",
        title="Cavrix Info",
        content_hash="hash1",
        size_bytes=200,
    )
    temp_store.insert_chunk(
        document_id=doc_id,
        chunk_index=0,
        chunk_identifier="Doc_1_Chunk_0",
        title="Founders Section",
        content="Cavrix Core was co-founded by Faaiz Johar and Mohd Fahad.",
        token_estimate=15,
    )
    temp_store.insert_chunk(
        document_id=doc_id,
        chunk_index=1,
        chunk_identifier="Doc_1_Chunk_1",
        title="Mission Section",
        content="The mission is building technology for what comes next.",
        token_estimate=12,
    )

    # Search for founder name
    results = temp_store.search_fts("Faaiz Johar", collection="cavrix", limit=5)
    assert len(results) == 1
    assert results[0].chunk_identifier == "Doc_1_Chunk_0"
    assert "Faaiz Johar" in results[0].content


def test_memory_crud_operations(temp_store):
    # Set memory
    mem = temp_store.set_memory("project_lead", "Faaiz Johar", category="team")
    assert mem.key == "project_lead"
    assert mem.value == "Faaiz Johar"

    # Get memory
    retrieved = temp_store.get_memory("project_lead")
    assert retrieved is not None
    assert retrieved.value == "Faaiz Johar"

    # Update memory
    temp_store.set_memory("project_lead", "Faaiz Johar (Lead)", category="team")
    updated = temp_store.get_memory("project_lead")
    assert updated.value == "Faaiz Johar (Lead)"

    # List memories
    all_mems = temp_store.list_memories()
    assert len(all_mems) == 1

    # Delete memory
    deleted = temp_store.delete_memory("project_lead")
    assert deleted is True
    assert temp_store.get_memory("project_lead") is None
