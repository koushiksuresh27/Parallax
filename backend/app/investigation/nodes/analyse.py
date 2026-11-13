from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.config import settings
from app.investigation.state import InvestigationState

analyse_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an operational analyst examining evidence to answer a business question.

You will receive:
- The original question
- Structured evidence (SQL query results from an e-commerce database)
- Document evidence (relevant passages from uploaded documents)

Your job:
1. Identify concrete patterns in the data (e.g., "Sellers in state X have 30% higher delay rates").
2. Generate explanations that distinguish between:
   - FACTS: directly supported by the data
   - PATTERNS: observed correlations in the data
   - EXPLANATIONS: possible causal interpretations (clearly labelled as such)
3. Assign a confidence level: "high" (strong data support), "medium" (partial data), or "low" (insufficient evidence).

Return a JSON object with exactly these keys:
- "patterns": list of observed pattern strings
- "explanations": list of explanation strings (each prefixed with [FACT], [PATTERN], or [EXPLANATION])
- "confidence": "high" | "medium" | "low"
- "limitations": list of strings describing what data was missing or what could not be determined
"""),
    ("human", """Question: {question}

Structured Evidence:
{structured_evidence}

Document Evidence:
{document_evidence}
""")
])


def get_llm():
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )


async def analyse_evidence(state: InvestigationState) -> dict:
    """Analyse the fused evidence bundle, identify patterns, generate explanations."""
    llm = get_llm()
    chain = analyse_prompt | llm | JsonOutputParser()

    structured_str = "\n".join(
        f"- {e.get('content', '')}" for e in state.get("structured_evidence", [])
    ) or "No structured evidence available."

    document_str = "\n".join(
        f"- {e.get('content', '')}" for e in state.get("document_evidence", [])
    ) or "No document evidence available."

    result = await chain.ainvoke({
        "question": state["question"],
        "structured_evidence": structured_str,
        "document_evidence": document_str,
    })

    return {
        "patterns": result.get("patterns", []),
        "explanations": result.get("explanations", []),
        "confidence": result.get("confidence", "low"),
        "limitations": result.get("limitations", []),
        "current_node": "analyse_evidence",
    }

