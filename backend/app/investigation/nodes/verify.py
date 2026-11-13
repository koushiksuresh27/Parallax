from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.config import settings
from app.core.llm_client import get_chat_llm
from app.investigation.state import InvestigationState

verify_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a verification auditor. Cross-check analyst explanations against evidence.
Output JSON only with keys:
- "verified_explanations": list of verified explanation strings
- "confidence": "high" | "medium" | "low"
- "issues": list of brief issue strings (max 3)
Be concise. Do not write full paragraphs."""),
    ("human", """Question: {question}
Explanations to audit:
{explanations}

Available Evidence:
{structured_evidence}
{document_evidence}
""")
])


def get_llm():
    return get_chat_llm(temperature=0.0, max_tokens=350)


async def verify_findings(state: InvestigationState) -> dict:
    """Cross-check the analysis conclusions against the retrieved evidence with strict token bounds."""
    llm = get_llm()
    chain = verify_prompt | llm | JsonOutputParser()

    structured_str = "\n".join(
        f"- {e.get('content', '')[:300]}" for e in state.get("structured_evidence", [])
    ) or "None"

    document_str = "\n".join(
        f"- {e.get('content', '')[:300]}" for e in state.get("document_evidence", [])
    ) or "None"

    explanations_str = "\n".join(f"- {e}" for e in state.get("explanations", [])) or "None"

    try:
        result = await chain.ainvoke({
            "question": state["question"],
            "explanations": explanations_str,
            "structured_evidence": structured_str,
            "document_evidence": document_str,
        })
    except Exception as e:
        # Graceful fallback if JSON parsing or token limit reached
        result = {
            "confidence": "medium",
            "verified_explanations": state.get("explanations", []),
            "issues": [f"Verification partial parse: {str(e)[:100]}"]
        }

    new_confidence = result.get("confidence", state.get("confidence", "medium"))
    verified = result.get("verified_explanations", [])
    issues = result.get("issues", [])

    current_limitations = state.get("limitations", [])
    updated_limitations = current_limitations + issues

    return {
        "confidence": new_confidence,
        "explanations": verified if verified else state.get("explanations", []),
        "limitations": updated_limitations,
        "retry_count": state.get("retry_count", 0) + 1,
        "current_node": "verify_findings",
    }

