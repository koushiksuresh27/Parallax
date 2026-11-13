import uuid
import time
import json
from datetime import datetime

from app.core.config import settings
from app.core.database import async_session
from app.models.investigations import Investigation, InvestigationEvidence, InvestigationFinding
from app.investigation.state import InvestigationState
from app.investigation.workflow import get_compiled_workflow


async def run_investigation(investigation_id: uuid.UUID, question: str) -> None:
    """
    Execute the full LangGraph investigation workflow and persist results.
    Updates the Investigation record in PostgreSQL throughout.
    """
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    await _execute_workflow(investigation_id, question, checkpointer)


async def _execute_workflow(investigation_id: uuid.UUID, question: str, checkpointer) -> None:
    app = get_compiled_workflow(checkpointer=checkpointer)

    initial_state: InvestigationState = {
        "question": question,
        "plan": [],
        "doc_query": "",
        "structured_evidence": [],
        "document_evidence": [],
        "patterns": [],
        "explanations": [],
        "confidence": "low",
        "citations": [],
        "limitations": [],
        "final_report": "",
        "retry_count": 0,
        "current_node": "starting",
        "error": "",
        "metrics": {"node_timings_ms": {}, "total_duration_ms": 0.0},
    }

    config = {"configurable": {"thread_id": str(investigation_id)}}

    try:
        async with async_session() as session:
            inv = await session.get(Investigation, investigation_id)
            if inv:
                inv.status = "running"
                inv.current_node = "plan_investigation"
                await session.commit()

        # Run the workflow
        t_flow_start = time.perf_counter()
        node_timings = {}
        last_node_time = t_flow_start

        final_state = None
        async for event in app.astream(initial_state, config=config):
            now = time.perf_counter()
            for node_name, node_output in event.items():
                current_node = node_output.get("current_node", node_name)
                duration_ms = round((now - last_node_time) * 1000, 2)
                node_timings[node_name] = duration_ms
                last_node_time = now

                async with async_session() as session:
                    inv = await session.get(Investigation, investigation_id)
                    if inv:
                        inv.current_node = current_node
                        await session.commit()
                final_state = node_output

        total_flow_ms = round((time.perf_counter() - t_flow_start) * 1000, 2)

        if checkpointer:
            full_state = await app.aget_state(config)
            final_state = full_state.values
        else:
            final_state = await app.ainvoke(initial_state, config={
                "configurable": {"thread_id": str(uuid.uuid4())}
            })

        metrics_data = {
            "node_timings_ms": node_timings,
            "total_duration_ms": total_flow_ms,
        }
        if final_state is not None:
            final_state["metrics"] = metrics_data

        # Persist results to PostgreSQL
        async with async_session() as session:
            inv = await session.get(Investigation, investigation_id)
            if not inv:
                return

            inv.status = "completed"
            inv.current_node = "done"
            inv.completed_at = datetime.utcnow()

            # Save evidence
            for e in final_state.get("structured_evidence", []):
                evidence = InvestigationEvidence(
                    investigation_id=investigation_id,
                    source_type="structured",
                    record_id=e.get("record_id"),
                    content=e.get("content", ""),
                    relevance_score=e.get("relevance_score"),
                )
                session.add(evidence)

            for e in final_state.get("document_evidence", []):
                evidence = InvestigationEvidence(
                    investigation_id=investigation_id,
                    source_type="document",
                    record_id=e.get("source_id"),
                    content=e.get("content", ""),
                    relevance_score=e.get("relevance_score"),
                )
                session.add(evidence)

            # Save findings
            for pattern in final_state.get("patterns", []):
                finding = InvestigationFinding(
                    investigation_id=investigation_id,
                    finding_type="pattern",
                    content=pattern,
                    confidence=final_state.get("confidence"),
                )
                session.add(finding)

            for explanation in final_state.get("explanations", []):
                finding = InvestigationFinding(
                    investigation_id=investigation_id,
                    finding_type="explanation",
                    content=explanation,
                    confidence=final_state.get("confidence"),
                )
                session.add(finding)

            if final_state.get("final_report"):
                finding = InvestigationFinding(
                    investigation_id=investigation_id,
                    finding_type="report",
                    content=final_state["final_report"],
                    confidence=final_state.get("confidence"),
                )
                session.add(finding)

            # Save execution telemetry metrics
            telemetry_content = json.dumps(metrics_data)
            finding_metrics = InvestigationFinding(
                investigation_id=investigation_id,
                finding_type="telemetry",
                content=telemetry_content,
                confidence="high",
            )
            session.add(finding_metrics)

            await session.commit()

    except Exception as e:
        async with async_session() as session:
            inv = await session.get(Investigation, investigation_id)
            if inv:
                inv.status = "failed"
                inv.current_node = "error"
                await session.commit()
        print(f"Investigation {investigation_id} failed: {e}")
        raise
