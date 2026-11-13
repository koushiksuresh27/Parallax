"""
Information Retrieval Quality Benchmark
Measures:
1. Hit Rate @ 1, Hit Rate @ 3, Hit Rate @ 5
2. Mean Reciprocal Rank (MRR)
3. Structured SQL deterministic retrieval validity
"""
import asyncio
from typing import Dict, Any, List

from app.retrieval.semantic import retrieve_documents
from app.retrieval.structured import retrieve_structured

# Ground-truth evaluation queries based on the ingested logistics PDF & Olist data
RETRIEVAL_TEST_CASES = [
    {
        "query": "logistics distribution and fulfillment challenges",
        "expected_terms": ["logistics", "distribution", "fulfillment", "supply", "transport", "delivery"]
    },
    {
        "query": "carrier delivery delay factors and freight rates",
        "expected_terms": ["freight", "carrier", "delay", "delivery", "shipping", "cost"]
    },
    {
        "query": "regional transportation infrastructure in Brazil",
        "expected_terms": ["region", "infrastructure", "brazil", "corridor", "southeast", "transport"]
    },
    {
        "query": "warehouse dispatch operations and transit time",
        "expected_terms": ["warehouse", "dispatch", "transit", "time", "order", "inventory"]
    },
]


async def run_retrieval_benchmark() -> Dict[str, Any]:
    print("\n[BENCHMARK] Starting Information Retrieval Quality (Hit@k, MRR) Benchmark...")

    k_values = [1, 3, 5]
    hits = {k: 0 for k in k_values}
    reciprocal_ranks = []
    top_scores: List[float] = []

    for case in RETRIEVAL_TEST_CASES:
        query = case["query"]
        expected = [term.lower() for term in case["expected_terms"]]

        results = await retrieve_documents(query, k=5)
        found_rank = None

        for rank, doc in enumerate(results, start=1):
            content_lower = doc["content"].lower()
            if any(term in content_lower for term in expected):
                if found_rank is None:
                    found_rank = rank
                if doc.get("relevance_score") is not None:
                    top_scores.append(float(doc["relevance_score"]))

        for k in k_values:
            if found_rank is not None and found_rank <= k:
                hits[k] += 1

        reciprocal_ranks.append(1.0 / found_rank if found_rank is not None else 0.0)

        print(f" -> Query: '{query[:45]}...' => First Relevant Rank: {found_rank if found_rank else 'None'}")

    n = len(RETRIEVAL_TEST_CASES)
    mrr = sum(reciprocal_ranks) / n if n > 0 else 0.0

    semantic_results = {
        "queries_tested": n,
        "hit_rate_at_1": round((hits[1] / n) * 100, 1),
        "hit_rate_at_3": round((hits[3] / n) * 100, 1),
        "hit_rate_at_5": round((hits[5] / n) * 100, 1),
        "mean_reciprocal_rank": round(mrr, 3),
        "avg_relevance_score": round(sum(top_scores) / len(top_scores), 3) if top_scores else None,
    }

    print(f" -> Semantic Retrieval: Hit@1={semantic_results['hit_rate_at_1']}%, Hit@5={semantic_results['hit_rate_at_5']}%, MRR={semantic_results['mean_reciprocal_rank']}")

    # Structured SQL channel validation
    print(" -> Validating Structured SQL Channel...")
    sql_res = await retrieve_structured("How many customers are in the database?")
    sql_valid = len(sql_res) > 0 and sql_res[0].get("source_type") == "structured" and sql_res[0].get("relevance_score") == 1.0

    return {
        "semantic_retrieval": semantic_results,
        "structured_sql_channel_valid": sql_valid,
    }


if __name__ == "__main__":
    asyncio.run(run_retrieval_benchmark())

