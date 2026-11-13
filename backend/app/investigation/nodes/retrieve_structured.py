from app.investigation.state import InvestigationState
from app.retrieval.structured import retrieve_structured as sql_retrieve


async def retrieve_structured(state: InvestigationState) -> dict:
    """Execute SQL sub-queries from the plan against PostgreSQL."""
    all_evidence = []

    for sub_query in state.get("plan", []):
        try:
            results = await sql_retrieve(sub_query)
            all_evidence.extend(results)
        except Exception as e:
            print(f"SQL sub-query failed: {sub_query} — {e}")
            all_evidence.append({
                "source_type": "structured",
                "record_id": None,
                "content": f"Query failed: {sub_query} — {str(e)}",
                "relevance_score": 0.0,
            })

    return {
        "structured_evidence": all_evidence,
        "current_node": "retrieve_structured",
    }

