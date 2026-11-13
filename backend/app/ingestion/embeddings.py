import hashlib
import json
import asyncio
from typing import List
from fastembed import TextEmbedding

from app.core.config import settings
from app.core.redis_client import redis_client

from langchain_core.embeddings import Embeddings

EMBEDDING_CACHE_TTL = 86400  # 24 hours

_fastembed_model = None


def get_fastembed_model() -> TextEmbedding:
    global _fastembed_model
    if _fastembed_model is None:
        _fastembed_model = TextEmbedding(model_name=settings.EMBEDDING_MODEL)
    return _fastembed_model


class LocalFastEmbeddings(Embeddings):
    """LangChain compatible wrapper around local FastEmbed."""
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL):
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        model = get_fastembed_model()
        return [[float(x) for x in vec] for vec in model.embed(texts, batch_size=64)]

    def embed_query(self, text: str) -> List[float]:
        model = get_fastembed_model()
        return [float(x) for x in next(model.embed([text]))]

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> List[float]:
        return await asyncio.to_thread(self.embed_query, text)


def get_embeddings_model():
    return LocalFastEmbeddings()


async def get_or_compute_embedding(text: str) -> list[float]:
    """
    Get embedding for text, using Redis cache to avoid recomputation.
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
    High-performance batch embedding with multi-key Redis pipeline check.
    Uses FastEmbed vectorized SIMD batching for any uncached chunks.
    """
    if not texts:
        return []

    cache_keys = [f"emb:{hashlib.sha256(t.encode()).hexdigest()}" for t in texts]
    cached_values = await redis_client.mget(*cache_keys)

    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []

    for i, raw_cached in enumerate(cached_values):
        if raw_cached:
            results[i] = json.loads(raw_cached)
        else:
            uncached_indices.append(i)
            uncached_texts.append(texts[i])

    if uncached_texts:
        embeddings_model = get_embeddings_model()
        new_embeddings = await embeddings_model.aembed_documents(uncached_texts)
        pipe = redis_client.pipeline()
        for idx, embedding in zip(uncached_indices, new_embeddings):
            results[idx] = embedding
            cache_key = cache_keys[idx]
            pipe.set(cache_key, json.dumps(embedding), ex=EMBEDDING_CACHE_TTL)
        await pipe.execute()

    return results  # type: ignore
