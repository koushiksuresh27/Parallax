import hashlib
import json

from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.core.redis_client import redis_client

# Lazy/safe initialization for embeddings model
def get_embeddings_model():
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
    )

EMBEDDING_CACHE_TTL = 86400  # 24 hours


async def get_or_compute_embedding(text: str) -> list[float]:
    """
    Get embedding for text, using Redis cache to avoid redundant API calls.
    Cache key: emb:{sha256_of_text}
    """
    cache_key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    embeddings_model = get_embeddings_model()
    embedding = await embeddings_model.aembed_query(text)
    await redis_client.set(cache_key, json.dumps(embedding), ex=EMBEDDING_CACHE_TTL)
    return embedding


async def get_or_compute_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Batch embedding with per-text Redis cache.
    Texts already cached are skipped in the API call.
    """
    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []

    # Check cache for each text
    for i, text in enumerate(texts):
        cache_key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
        cached = await redis_client.get(cache_key)
        if cached:
            results[i] = json.loads(cached)
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    # Compute uncached embeddings in one API call
    if uncached_texts:
        embeddings_model = get_embeddings_model()
        new_embeddings = await embeddings_model.aembed_documents(uncached_texts)
        for idx, embedding in zip(uncached_indices, new_embeddings):
            results[idx] = embedding
            # Cache each new embedding
            text = texts[idx]
            cache_key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
            await redis_client.set(cache_key, json.dumps(embedding), ex=EMBEDDING_CACHE_TTL)

    return results  # type: ignore
