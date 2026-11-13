from app.investigation.state import InvestigationState
from app.retrieval.semantic import retrieve_documents as qdrant_retrieve


async def retrieve_documents(state: InvestigationState) -> dict:
    """Retrieve semantically relevant document chunks from Qdrant."""
    query = state.get("doc_query", state["question"])

    try:
        results = await qdrant_retrieve(query, k=5)
    except Exception as e:
        print(f"Document retrieval failed: {e}")
        results = []

    return {
        "document_evidence": results,
        "current_node": "retrieve_documents",
    }

