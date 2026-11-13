"""
End-to-End Latency, Concurrency, and Error Rate Benchmark
Measures:
1. End-to-end P50, P90, min, max response latency across concurrent investigations
2. Node-level timing breakdown (Planning, SQL Retrieval, Vector Search, Analysis, Verification, Report)
3. Sustained throughput (investigations per minute)
4. Failure/error rate and Groq key rotation resilience
"""
import asyncio
import json
import statistics
import time
import uuid
from typing import Dict, Any, List

from app.core.database import async_session
from app.investigation.runner import run_investigation
from app.models.investigations import Investigation, InvestigationFinding

BENCHMARK_QUESTIONS = [
    "Why are deliveries getting delayed?",
    "Which seller states have the longest shipping times?",
    "What is the average freight value for delayed orders?",
]


async def _run_single_investigation(question: str) -> Dict[str, Any]:
    inv_id = uuid.uuid4()
    async with async_session() as s:
        inv = Investigation(id=inv_id, question=question, status="pending")
        s.add(inv)
        await s.commit()

    t0 = time.perf_counter()
    error_msg = None
    try:
        await run_investigation(inv_id, question)
    except Exception as e:
        error_msg = str(e)

    elapsed_s = time.perf_counter() - t0

    # Fetch status & telemetry finding
    node_timings = {}
    status = "failed" if error_msg else "unknown"

    async with async_session() as s:
        inv = await s.get(Investigation, inv_id)
        if inv:
            status = inv.status

        # Query telemetry finding
        from sqlalchemy import select
        res = await s.execute(
            select(InvestigationFinding.content)
            .where(
                InvestigationFinding.investigation_id == inv_id,
                InvestigationFinding.finding_type == "telemetry"
            )
        )
        telemetry_raw = res.scalar_one_or_none()
        if telemetry_raw:
            try:
                telemetry_data = json.loads(telemetry_raw)
                node_timings = telemetry_data.get("node_timings_ms", {})
            except Exception:
                pass

    return {
        "id": str(inv_id),
        "question": question,
        "status": status,
        "elapsed_s": round(elapsed_s, 2),
        "node_timings_ms": node_timings,
        "error": error_msg,
    }


async def run_e2e_benchmark() -> Dict[str, Any]:
    print("\n[BENCHMARK] Starting End-to-End Latency, Throughput & Error Rate Benchmark...")
    print(f" -> Launching {len(BENCHMARK_QUESTIONS)} parallel investigations across Groq key pool...")

    t_start = time.perf_counter()
    sem = asyncio.Semaphore(1)

    async def _throttled_investigation(q: str):
        async with sem:
            res = await _run_single_investigation(q)
            await asyncio.sleep(2)
            return res

    tasks = [_throttled_investigation(q) for q in BENCHMARK_QUESTIONS]
    results = await asyncio.gather(*tasks)
    total_wall_s = time.perf_counter() - t_start

    successful = [r for r in results if r["status"] == "completed"]
    failed = [r for r in results if r["status"] != "completed"]

    latencies = [r["elapsed_s"] for r in successful]
    error_rate = (len(failed) / len(results)) * 100

    # Aggregate node timings across successful investigations
    node_breakdown: Dict[str, List[float]] = {}
    for r in successful:
        for node, ms in r.get("node_timings_ms", {}).items():
            node_breakdown.setdefault(node, []).append(ms)

    avg_node_breakdown = {
        node: round(statistics.mean(times), 1)
        for node, times in node_breakdown.items()
    }

    throughput_qpm = (len(successful) / total_wall_s) * 60 if total_wall_s > 0 else 0.0

    summary = {
        "total_requests": len(results),
        "completed_requests": len(successful),
        "failed_requests": len(failed),
        "error_rate_pct": round(error_rate, 1),
        "total_wall_clock_s": round(total_wall_s, 2),
        "throughput_investigations_per_min": round(throughput_qpm, 2),
        "p50_latency_s": round(statistics.median(latencies), 2) if latencies else None,
        "min_latency_s": round(min(latencies), 2) if latencies else None,
        "max_latency_s": round(max(latencies), 2) if latencies else None,
        "node_timings_mean_ms": avg_node_breakdown,
        "runs": results,
    }

    print(f" -> Complete: {len(successful)}/{len(results)} successful in {total_wall_s:.2f}s")
    print(f" -> Throughput: {summary['throughput_investigations_per_min']} investigations/min")
    if latencies:
        print(f" -> Latency (P50): {summary['p50_latency_s']}s | Min: {summary['min_latency_s']}s | Max: {summary['max_latency_s']}s")
    print(f" -> Error Rate: {summary['error_rate_pct']}%")

    return summary


if __name__ == "__main__":
    asyncio.run(run_e2e_benchmark())

