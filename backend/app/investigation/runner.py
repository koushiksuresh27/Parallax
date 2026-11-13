import uuid
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
    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        async with AsyncRedisSaver.from_conn_string(settings.REDIS_URL) as checkpointer:
            await _execute_workflow(investigation_id, question, checkpointer)
    except Exception as e:
        print(f"Redis checkpointer context error ({e}), running without checkpointer:")
        await _execute_workflow(investigation_id, question, None)


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
        final_state = None
        async for event in app.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                current_node = node_output.get("current_node", node_name)
                async with async_session() as session:
                    inv = await session.get(Investigation, investigation_id)
                    if inv:
                        inv.current_node = current_node
                        await session.commit()
                final_state = node_output

        if checkpointer:
            full_state = await app.aget_state(config)
            final_state = full_state.values
        else:
            final_state = await app.ainvoke(initial_state, config={
                "configurable": {"thread_id": str(uuid.uuid4())}
            })

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
