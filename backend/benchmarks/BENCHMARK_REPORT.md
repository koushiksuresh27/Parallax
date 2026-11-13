# Parallax Operational Intelligence — Empirical Benchmark Report

**Generated At:** 2026-11-14 02:39:13  
**Hardware / Environment:** Local Host (Windows x86_64, Docker PostgreSQL 15, Qdrant, Redis 7)  
**LLM Engine:** Groq API Pool (qwen/qwen3.8-27b, 6 Rotated Keys)  
**Embeddings:** Local ONNX FastEmbed (`BAAI/bge-small-en-v1.5`, 384 dimensions)  

---

## 1. Document Chunking Efficiency

| Metric | Measured Value | Standard Target | Status |
| :--- | :--- | :--- | :--- |
| **Ingestion Throughput** | **12,176,882 chars/sec** | > 50,000 chars/sec | ✅ High Speed |
| **Average Chunk Size** | **991.9 chars** | 1000 ± 200 chars | ✅ Within Spec |
| **Chunk Size Standard Dev (σ)** | **37.06 chars** | < 250 chars | ✅ Low Variance |
| **Min / Max Chunk Size** | **641 / 999 chars** | <= 1000 chars | ✅ Within Bounds |
| **Empty Chunk Count** | **0** | 0 | ✅ Zero Waste |

---

## 2. Embedding Performance & Caching

| Metric | Measured Value | Unit |
| :--- | :--- | :--- |
| **Cold Embedding Compute (ONNX CPU)** | **23.8** | ms / chunk |
| **Cached Embedding Latency (Redis)** | **0.32** | ms / chunk |
| **Redis Cache Speedup Factor** | **75.3x** | Multiplier |
| **Total Cold Batch Time (30 chunks)** | **714.04** | ms |
| **Total Cached Batch Time (30 chunks)** | **9.49** | ms |

> *Observation:* Fetching pre-computed embeddings from Redis yields a **75.3x speedup**, completely eliminating embedding latency on re-investigation or repeated document passages.

---

## 3. Retrieval Quality (Information Retrieval Standard)

| Information Retrieval Metric | Result | Description |
| :--- | :--- | :--- |
| **Hit Rate @ 1** | **100.0%** | Top-1 chunk contains ground-truth domain relevance |
| **Hit Rate @ 3** | **100.0%** | Top-3 chunks contain ground-truth domain relevance |
| **Hit Rate @ 5** | **100.0%** | Top-5 chunks contain ground-truth domain relevance |
| **Mean Reciprocal Rank (MRR)** | **1.0** | Rank position inverse score (Scale 0.0 - 1.0) |
| **Structured SQL Channel** | **Validated (100% Deterministic)** | LangChain SQL generation executed against PostgreSQL |

---

## 4. End-to-End Latency Profile & Throughput

### Latency Summary (Concurrent Investigations)
- **Completed Investigations:** 3 / 3
- **Sustained Throughput:** **4.12 investigations / minute**
- **Median Latency ($P_50$):** **11.67 seconds**
- **Min Latency:** 11.48 seconds
- **Max Latency:** 14.47 seconds
- **Overall Error Rate:** **0.0%**

### Per-Node Execution Breakdown (Mean Milliseconds)
```
[START]
   │
   ▼
[Plan Investigation]     --> 1130.8 ms
   │
   ▼
[Retrieve Structured]    --> 5632.9 ms (SQL over PostgreSQL)
   │
   ▼
[Retrieve Documents]     --> 280.5 ms (Vector similarity over Qdrant)
   │
   ▼
[Analyse Evidence]       --> 1633.3 ms (Groq Llama 3.3 70B)
   │
   ▼
[Verify Findings]        --> 1238.4 ms (Groq Cross-check)
   │
   ▼
[Generate Report]        --> 2543.1 ms (Cited output assembly)
   │
   ▼
[END]
```

---
*All values measured empirically using `time.perf_counter()` on live services. No simulated figures.*
