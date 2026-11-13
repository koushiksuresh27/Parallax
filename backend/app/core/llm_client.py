"""
Adapter to integrate groq_pool key rotation with LangChain and ChatOpenAI interfaces.
"""
from langchain_groq import ChatGroq
from app.core.config import settings
from groq_manager import groq_pool


def get_chat_llm(temperature: float = 0.0, model: str = None, max_tokens: int = 750) -> ChatGroq:
    """
    Returns a ChatGroq instance using a round-robin rotated key from groq_pool
    to distribute rate limits across all 6 API keys.
    """
    slot = groq_pool.rotate_to_next(reason="Round-robin load distribution")
    selected_model = model or settings.GROQ_MODEL
    return ChatGroq(
        model=selected_model,
        temperature=temperature,
        groq_api_key=slot.key,
        max_tokens=max_tokens,
        max_retries=3,
    )

