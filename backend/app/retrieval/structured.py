import hashlib
import json

from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.redis_client import redis_client

# Cache TTL for SQL query results (PRD §5 Purpose 2)
QUERY_CACHE_TTL = 600  # 10 minutes

# Only expose Olist tables to the LLM — not internal tables
OLIST_TABLES = [
    "olist_orders",
    "olist_order_items",
    "olist_customers",
    "olist_sellers",
    "olist_products",
    "olist_reviews",
]


def get_sql_database() -> SQLDatabase:
    """Get a LangChain SQLDatabase instance connected to the Olist tables only."""
    return SQLDatabase.from_uri(
        settings.DATABASE_URL_SYNC,
        include_tables=OLIST_TABLES,
        sample_rows_in_table_info=3,
    )


def get_sql_chain():
    """Create a LangChain SQL query chain for natural language → SQL."""
    db = get_sql_database()
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    return create_sql_query_chain(llm, db)


async def retrieve_structured(query: str) -> list[dict]:
    """
    Translate a natural language query into SQL, execute it, and return results.
    Uses Redis cache for identical SQL queries (PRD §5 Purpose 2).
    Returns list of dicts with keys: source_type, record_id, content, relevance_score.
    """
    try:
        # Generate SQL from natural language
        chain = get_sql_chain()
        sql = await chain.ainvoke({"question": query})

        # Clean the SQL — remove markdown fencing if present
        sql = sql.strip()
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[-1]  # Remove first line
        if sql.endswith("```"):
            sql = sql.rsplit("```", 1)[0]
        sql = sql.strip()

        # Check Redis cache
        cache_key = f"query:{hashlib.md5(sql.encode()).hexdigest()}"
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Execute SQL
        db = get_sql_database()
        raw_result = db.run(sql)

        # Parse results into evidence format
        results = []
        if raw_result and raw_result.strip():
            results.append({
                "source_type": "structured",
                "record_id": None,
                "content": f"SQL: {sql}\n\nResult:\n{raw_result}",
                "relevance_score": 1.0,
                "sql_query": sql,
            })

        # Cache the result
        await redis_client.set(cache_key, json.dumps(results), ex=QUERY_CACHE_TTL)

        return results

    except Exception as e:
        print(f"Structured retrieval error: {e}")
        return [{
            "source_type": "structured",
            "record_id": None,
            "content": f"SQL retrieval failed: {str(e)}",
            "relevance_score": 0.0,
        }]

