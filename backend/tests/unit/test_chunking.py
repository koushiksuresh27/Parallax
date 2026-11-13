import pytest
from app.ingestion.document_processor import chunk_document

SAMPLE_TEXT = "word " * 2000  # 10000 chars, well above one chunk


def test_chunks_within_size_bounds():
    chunks = chunk_document(SAMPLE_TEXT, source_id="test-uuid-001", filename="test.pdf")
    for chunk in chunks:
        assert len(chunk["content"]) <= 1000
        assert len(chunk["content"]) > 0


def test_no_empty_chunks():
    chunks = chunk_document(SAMPLE_TEXT, source_id="test-uuid-001", filename="test.pdf")
    assert all(chunk["content"].strip() != "" for chunk in chunks)


def test_all_chunks_have_required_metadata():
    chunks = chunk_document(SAMPLE_TEXT, source_id="test-uuid-001", filename="test.pdf")
    required_keys = {"content", "source_id", "page_number", "chunk_index", "char_count"}
    for chunk in chunks:
        assert required_keys.issubset(chunk.keys()), f"Missing keys in chunk: {chunk.keys()}"


def test_source_id_propagated_to_all_chunks():
    chunks = chunk_document(SAMPLE_TEXT, source_id="test-uuid-001", filename="test.pdf")
    assert all(chunk["source_id"] == "test-uuid-001" for chunk in chunks)


def test_chunk_index_is_sequential():
    chunks = chunk_document(SAMPLE_TEXT, source_id="test-uuid-001", filename="test.pdf")
    for i, chunk in enumerate(chunks):
        assert chunk["chunk_index"] == i


def test_single_short_text_produces_one_chunk():
    short_text = "This is a short document."
    chunks = chunk_document(short_text, source_id="test-uuid-002", filename="short.pdf")
    assert len(chunks) == 1

