import re
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from app.core.config import settings
from app.ingestion.embeddings import get_embeddings_model

STOPWORDS = {
    "what", "why", "how", "when", "where", "which", "who", "the", "and", "are",
    "for", "with", "about", "from", "into", "that", "this", "have", "has", "had", "been"
}

_vector_store: QdrantVectorStore | None = None


def get_vector_store() -> QdrantVectorStore:
    """Singleton instance for QdrantVectorStore to avoid reconnecting on each invocation."""
    global _vector_store
    if _vector_store is None:
        client = QdrantClient(url=settings.QDRANT_URL)
        _vector_store = QdrantVectorStore(
            client=client,
            collection_name=settings.QDRANT_COLLECTION,
            embedding=get_embeddings_model(),
            content_payload_key="content",
        )
    return _vector_store


def get_semantic_retriever(k: int = 5):
    """Returns a LangChain retriever backed by the Qdrant parallax_documents collection."""
    vs = get_vector_store()
    return vs.as_retriever(search_kwargs={"k": k})


async def retrieve_documents(query: str, k: int = 5) -> list[dict]:
    """
    Retrieve top-k semantically and lexically relevant document chunks.
    Uses hybrid re-ranking over candidate pool (2*k) to ensure high Hit@1 and MRR.
    Returns list of dicts with keys: source_type, content, source_id, page_number, chunk_index, relevance_score.
    """
    vs = get_vector_store()
    candidate_k = max(k * 2, 10)

    # Fetch candidate pool with similarity scores
    candidates = vs.similarity_search_with_score(query, k=candidate_k)

    query_terms = [
        t for t in re.findall(r"\b[a-zA-Z]{3,}\b", query.lower())
        if t not in STOPWORDS
    ]

    scored_results = []
    for doc, score in candidates:
        content = doc.page_content or ""
        content_lower = content.lower()
        matches = sum(1 for term in query_terms if term in content_lower)
        # Blend dense cosine similarity with lexical exact-term bonus
        hybrid_score = (score or 0.5) + (0.12 * matches)
        scored_results.append((hybrid_score, doc, score))

    scored_results.sort(key=lambda x: x[0], reverse=True)

    results = []
    for hybrid_score, doc, original_score in scored_results[:k]:
        results.append({
            "source_type": "document",
            "content": doc.page_content,
            "source_id": doc.metadata.get("source_id", ""),
            "page_number": doc.metadata.get("page_number"),
            "chunk_index": doc.metadata.get("chunk_index"),
            "relevance_score": round(float(original_score), 4) if original_score is not None else None,
        })

    return results

