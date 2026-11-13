from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from app.core.config import settings
from app.ingestion.embeddings import get_embeddings_model


def get_semantic_retriever(k: int = 5):
    """
    Returns a LangChain retriever backed by the Qdrant parallax_documents collection.
    Uses the same embeddings model used during ingestion.
    """
    client = QdrantClient(url=settings.QDRANT_URL)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=settings.QDRANT_COLLECTION,
        embedding=get_embeddings_model(),
    )

    return vector_store.as_retriever(search_kwargs={"k": k})


async def retrieve_documents(query: str, k: int = 5) -> list[dict]:
    """
    Retrieve top-k semantically relevant document chunks for a query.
    Returns list of dicts with keys: source_type, content, source_id, page_number, chunk_index, relevance_score.
    """
    retriever = get_semantic_retriever(k=k)
    docs = await retriever.ainvoke(query)

    results = []
    for doc in docs:
        results.append({
            "source_type": "document",
            "content": doc.page_content,
            "source_id": doc.metadata.get("source_id", ""),
            "page_number": doc.metadata.get("page_number"),
            "chunk_index": doc.metadata.get("chunk_index"),
            "relevance_score": doc.metadata.get("score"),
        })

    return results

