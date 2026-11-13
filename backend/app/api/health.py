from fastapi import APIRouter
from sqlalchemy import text
from qdrant_client import QdrantClient

from app.core.config import settings
from app.core.database import async_session
from app.core.redis_client import redis_client

router = APIRouter()


@router.get("/health")
async def health_check():
    result = {}

    # Postgres
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        result["postgres"] = "ok"
    except Exception as e:
        result["postgres"] = f"error: {str(e)}"

    # Redis
    try:
        pong = await redis_client.ping()
        result["redis"] = "ok" if pong else "error: no pong"
    except Exception as e:
        result["redis"] = f"error: {str(e)}"

    # Qdrant
    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        client.get_collections()
        result["qdrant"] = "ok"
    except Exception as e:
        result["qdrant"] = f"error: {str(e)}"

    return result

