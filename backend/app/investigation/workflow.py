from langgraph.graph import StateGraph, START, END

from app.investigation.state import InvestigationState
from app.investigation.nodes.plan import plan_investigation
from app.investigation.nodes.retrieve_structured import retrieve_structured
from app.investigation.nodes.retrieve_documents import retrieve_documents
from app.investigation.nodes.analyse import analyse_evidence
from app.investigation.nodes.verify import verify_findings
from app.investigation.nodes.report import generate_report


def route_after_retrieval(state: InvestigationState) -> str:
    """Skip analysis if no evidence was found from either channel."""
    has_structured = bool(state.get("structured_evidence"))
    has_documents = bool(state.get("document_evidence"))

    if not has_structured and not has_documents:
        return "generate_report"  # Skip analysis — nothing to work with
    return "analyse_evidence"


def route_after_verification(state: InvestigationState) -> str:
    """Retry analysis once if confidence is low."""
    if state.get("confidence") == "low" and state.get("retry_count", 0) < 1:
        return "analyse_evidence"  # One retry
    return "generate_report"


def build_workflow() -> StateGraph:
    """Build the investigation workflow graph."""
    workflow = StateGraph(InvestigationState)

    # Add nodes
    workflow.add_node("plan_investigation", plan_investigation)
    workflow.add_node("retrieve_structured", retrieve_structured)
    workflow.add_node("retrieve_documents", retrieve_documents)
    workflow.add_node("analyse_evidence", analyse_evidence)
    workflow.add_node("verify_findings", verify_findings)
    workflow.add_node("generate_report", generate_report)

    # Wire edges
    workflow.add_edge(START, "plan_investigation")
    workflow.add_edge("plan_investigation", "retrieve_structured")
    workflow.add_edge("retrieve_structured", "retrieve_documents")

    # Conditional: after retrieval, skip analysis if no evidence
    workflow.add_conditional_edges(
        "retrieve_documents",
        route_after_retrieval,
        {
            "analyse_evidence": "analyse_evidence",
            "generate_report": "generate_report",
        },
    )

    workflow.add_edge("analyse_evidence", "verify_findings")

    # Conditional: after verification, retry or proceed to report
    workflow.add_conditional_edges(
        "verify_findings",
        route_after_verification,
        {
            "analyse_evidence": "analyse_evidence",
            "generate_report": "generate_report",
        },
    )

    workflow.add_edge("generate_report", END)

    return workflow


def get_compiled_workflow(checkpointer=None):
    """Compile the workflow, optionally with a Redis checkpointer."""
    workflow = build_workflow()
    return workflow.compile(checkpointer=checkpointer)

