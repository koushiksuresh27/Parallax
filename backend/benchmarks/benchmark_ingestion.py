"""
Ingestion & Embedding Benchmark
Measures:
1. Document chunking speed (chars/sec, chunks/sec) and chunk size distribution
2. Embedding throughput (cold compute vs Redis cache hit latency & speedup multiplier)
"""
import asyncio
import hashlib
import statistics
import time
from typing import Dict, Any

from app.ingestion.document_processor import chunk_document
from app.ingestion.embeddings import (
    get_or_compute_embeddings_batch,
    redis_client,
)


async def run_ingestion_benchmark() -> Dict[str, Any]:
    print("\n[BENCHMARK] Starting Chunking & Embedding Benchmark...")

    # 1. Chunking Benchmark
    sample_text = (
        "Logistics operational intelligence report: Carrier fulfillment delay record. "
        "Estimated delivery timelines depend on warehouse dispatch velocity, "
        "interstate transport corridors, and regional customs clearances. "
    ) * 350  # ~65,000 chars

    iterations = 25
    chunk_times = []

    for _ in range(iterations):
        t0 = time.perf_counter()
        chunks = chunk_document(sample_text, source_id="benchmark-uuid", filename="benchmark.txt")
        t1 = time.perf_counter()
        chunk_times.append(t1 - t0)

    avg_chunk_time = statistics.mean(chunk_times)
    throughput_chars_sec = len(sample_text) / avg_chunk_time
    sizes = [c["char_count"] for c in chunks]

    chunking_metrics = {
        "text_length_chars": len(sample_text),
        "total_chunks": len(chunks),
        "avg_chunking_ms": round(avg_chunk_time * 1000, 2),
        "throughput_chars_per_sec": round(throughput_chars_sec, 0),
        "mean_chunk_size": round(statistics.mean(sizes), 1),
        "stdev_chunk_size": round(statistics.stdev(sizes), 2),
        "min_chunk_size": min(sizes),
        "max_chunk_size": max(sizes),
        "empty_chunks_count": sum(1 for s in sizes if s == 0),
    }

    print(" -> Chunking throughput: {:,.0f} chars/sec (mean size: {} chars)".format(
        chunking_metrics["throughput_chars_per_sec"],
        chunking_metrics["mean_chunk_size"]
    ))

    # 2. Embedding Benchmark (Cold vs Redis Cache Hit)
    test_texts = [
        f"Carrier logistics order #{i}: Freight transit between Sao Paulo and Rio de Janeiro"
        for i in range(30)
    ]

    # Clear existing benchmark cache keys
    for text in test_texts:
        key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
        await redis_client.delete(key)

    # Cold Run (FastEmbed ONNX CPU compute)
    t0 = time.perf_counter()
    _ = await get_or_compute_embeddings_batch(test_texts)
    t_cold = time.perf_counter() - t0

    # Warm Run (Redis Cache Hit)
    t0 = time.perf_counter()
    _ = await get_or_compute_embeddings_batch(test_texts)
    t_warm = time.perf_counter() - t0

    speedup = t_cold / t_warm if t_warm > 0 else float("inf")

    embedding_metrics = {
        "chunk_count": len(test_texts),
        "cold_total_ms": round(t_cold * 1000, 2),
        "cold_ms_per_chunk": round((t_cold / len(test_texts)) * 1000, 2),
        "cached_total_ms": round(t_warm * 1000, 2),
        "cached_ms_per_chunk": round((t_warm / len(test_texts)) * 1000, 2),
        "cache_speedup_multiplier": round(speedup, 1),
    }

    print(" -> Cold embedding: {:.2f} ms/chunk | Cached embedding: {:.2f} ms/chunk (Speedup: {}x)".format(
        embedding_metrics["cold_ms_per_chunk"],
        embedding_metrics["cached_ms_per_chunk"],
        embedding_metrics["cache_speedup_multiplier"]
    ))

    return {
        "chunking": chunking_metrics,
        "embedding": embedding_metrics,
    }


if __name__ == "__main__":
    asyncio.run(run_ingestion_benchmark())

