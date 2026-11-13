from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.investigation.state import InvestigationState

report_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a report writer for an operational intelligence platform.

Generate a clear, structured investigation report that:

1. States the question being investigated
2. Summarises the key findings with inline citations
3. Distinguishes between FACTS (from data), PATTERNS (correlations), and EXPLANATIONS (interpretations)
4. Lists specific evidence references using [SQL-N] for structured data and [DOC-N] for document passages
5. Notes any limitations or gaps in the analysis
6. States the overall confidence level

Format the report in markdown with clear sections:
## Investigation: <question>
### Key Findings
### Evidence Summary
### Limitations
### Confidence: <high|medium|low>

Every claim must have a citation reference. Do not make claims without supporting evidence.
"""),
    ("human", """Question: {question}

Confidence: {confidence}

Patterns:
{patterns}

Explanations:
{explanations}

Structured Evidence (cite as [SQL-1], [SQL-2], etc.):
{structured_evidence}

Document Evidence (cite as [DOC-1], [DOC-2], etc.):
{document_evidence}

Limitations:
{limitations}
""")
])


def get_llm():
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )


async def generate_report(state: InvestigationState) -> dict:
    """Assemble the final cited investigation report."""
    llm = get_llm()
    chain = report_prompt | llm

    structured_items = state.get("structured_evidence", [])
    document_items = state.get("document_evidence", [])

    structured_str = "\n".join(
        f"[SQL-{i+1}] {e.get('content', '')}" for i, e in enumerate(structured_items)
    ) or "No structured evidence retrieved."

    document_str = "\n".join(
        f"[DOC-{i+1}] {e.get('content', '')}" for i, e in enumerate(document_items)
    ) or "No document evidence retrieved."

    patterns_str = "\n".join(f"- {p}" for p in state.get("patterns", [])) or "No patterns identified."
    explanations_str = "\n".join(f"- {e}" for e in state.get("explanations", [])) or "No explanations generated."
    limitations_str = "\n".join(f"- {l}" for l in state.get("limitations", [])) or "None noted."

    result = await chain.ainvoke({
        "question": state["question"],
        "confidence": state.get("confidence", "low"),
        "patterns": patterns_str,
        "explanations": explanations_str,
        "structured_evidence": structured_str,
        "document_evidence": document_str,
        "limitations": limitations_str,
    })

    citations = []
    for i, e in enumerate(structured_items):
        citations.append({
            "ref": f"SQL-{i+1}",
            "source_type": "structured",
            "content": e.get("content", "")[:200],
            "record_id": e.get("record_id"),
        })
    for i, e in enumerate(document_items):
        citations.append({
            "ref": f"DOC-{i+1}",
            "source_type": "document",
            "content": e.get("content", "")[:200],
            "source_id": e.get("source_id"),
            "page_number": e.get("page_number"),
            "chunk_index": e.get("chunk_index"),
        })

    return {
        "final_report": result.content,
        "citations": citations,
        "current_node": "generate_report",
    }

