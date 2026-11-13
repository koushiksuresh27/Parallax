"""
Integration tests for the retrieval module.
Requires: Olist data in PostgreSQL, at least one document in Qdrant.
Run: cd backend && .\.venv\Scripts\python -m pytest tests/test_retrieval.py -v -s
"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_evidence_fusion():
    """Test that fusion merges both channels into a single list."""
    from app.retrieval.fusion import fuse_evidence

    structured = [{"source_type": "structured", "record_id": "ord_1", "content": "10 orders", "relevance_score": 1.0}]
    documents = [{"source_type": "document", "content": "Logistics report", "relevance_score": 0.8, "source_id": "abc", "page_number": 1, "chunk_index": 0}]

    evidence = await fuse_evidence(structured, documents)

    assert len(evidence) == 2
    assert evidence[0]["source_type"] == "structured"  # Higher relevance first
    assert evidence[1]["source_type"] == "document"


@pytest.mark.asyncio
async def test_semantic_retrieval():
    """Test that Qdrant returns document chunks for a relevant query."""
    from app.retrieval.semantic import retrieve_documents

    results = await retrieve_documents("delivery delays logistics", k=3)
    print(f"Semantic results: {len(results)} documents")
    for r in results:
        print(f"  - [{r['source_type']}] chunk_index={r.get('chunk_index')}: {r['content'][:100]}...")

    assert isinstance(results, list)
    for r in results:
        assert r["source_type"] == "document"
        assert "content" in r


@pytest.mark.asyncio
async def test_structured_retrieval_and_cache():
    """Test that SQL chain runs and results are cached in Redis."""
    from app.retrieval.structured import retrieve_structured
    from app.core.redis_client import redis_client

    mock_sql = "SELECT count(*) FROM olist_customers;"
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_sql)

    with patch("app.retrieval.structured.get_sql_chain", return_value=mock_chain):
        # First call — cache miss
        results1 = await retrieve_structured("What is the total number of customers?")
        assert len(results1) > 0
        assert results1[0]["source_type"] == "structured"
        assert "2" in results1[0]["content"]

        keys_before = await redis_client.keys("query:*")

        # Second call — should hit Redis cache directly without calling LLM chain again
        results2 = await retrieve_structured("What is the total number of customers?")
        keys_after = await redis_client.keys("query:*")

        assert len(keys_after) == len(keys_before)
        assert results1 == results2
