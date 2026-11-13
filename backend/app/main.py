from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.database import engine
from app.core.redis_client import redis_client
from app.api.health import router as health_router
from app.api.sources import router as sources_router
from app.api.investigations import router as investigations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Parallax API starting up...")
    # Verify DB connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    print("PostgreSQL connected.")

    # Verify Redis
    await redis_client.ping()
    print("Redis connected.")

    # Ensure Qdrant collection exists
    from app.ingestion.doc_processor import ensure_qdrant_collection
    ensure_qdrant_collection()
    print("Qdrant collection ready.")

    yield

    # Shutdown
    await engine.dispose()
    await redis_client.aclose()
    print("Parallax API shut down.")


app = FastAPI(
    title="Parallax",
    description="AI-powered operational intelligence platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(sources_router, prefix="/api")
app.include_router(investigations_router, prefix="/api")
