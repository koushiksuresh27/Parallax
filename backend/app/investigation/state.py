from typing import TypedDict


class InvestigationState(TypedDict):
    question: str                    # Original analyst question
    plan: list[str]                  # Sub-queries from planning node
    doc_query: str                   # Semantic search query for documents
    structured_evidence: list[dict]  # Records from PostgreSQL
    document_evidence: list[dict]    # Chunks from Qdrant
    patterns: list[str]             # Identified patterns
    explanations: list[str]         # LLM-generated explanations
    confidence: str                 # "high" | "medium" | "low"
    citations: list[dict]           # Source references
    limitations: list[str]          # What was missing
    final_report: str               # Assembled investigation report
    retry_count: int                # Tracks verification retries
    current_node: str               # For frontend progress tracking
    error: str                      # Error message if something fails
    metrics: dict                   # Telemetry timings & metrics

