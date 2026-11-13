async def fuse_evidence(
    structured_results: list[dict],
    document_results: list[dict],
) -> list[dict]:
    """
    Merge structured (SQL) and document (Qdrant) retrieval results
    into a single labelled evidence bundle.
    Each item carries its source_type so the LLM knows provenance.
    """
    evidence = []

    for item in structured_results:
        evidence.append({
            "source_type": "structured",
            "record_id": item.get("record_id"),
            "content": item.get("content", ""),
            "relevance_score": item.get("relevance_score", 0.0),
            "metadata": {
                "sql_query": item.get("sql_query"),
            },
        })

    for item in document_results:
        evidence.append({
            "source_type": "document",
            "record_id": None,
            "content": item.get("content", ""),
            "relevance_score": item.get("relevance_score", 0.0),
            "metadata": {
                "source_id": item.get("source_id"),
                "page_number": item.get("page_number"),
                "chunk_index": item.get("chunk_index"),
            },
        })

    # Sort by relevance (highest first), structured results first within same score
    evidence.sort(
        key=lambda x: (x["relevance_score"] or 0.0),
        reverse=True,
    )

    return evidence

