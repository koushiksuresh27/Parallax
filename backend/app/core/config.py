import os
from pydantic_settings import BaseSettings

# Root directory is two levels up from backend/app/core (i.e. parallax/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ENV_PATH = os.path.join(ROOT_DIR, ".env")


class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://parallax:changeme_in_production@localhost:5432/parallax"
    # For Alembic (sync driver)
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://parallax:changeme_in_production@localhost:5432/parallax"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    QDRANT_COLLECTION: str = "parallax_documents"
    EMBEDDING_DIMENSION: int = 1536

    # App
    APP_ENV: str = "development"

    model_config = {"env_file": ENV_PATH, "extra": "ignore"}


settings = Settings()

