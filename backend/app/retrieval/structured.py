import hashlib
import json
import re

from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis_client import redis_client
from app.core.llm_client import get_chat_llm

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


_cached_sql_db: SQLDatabase | None = None


def get_sql_database() -> SQLDatabase:
    """Get a cached LangChain SQLDatabase instance connected to the Olist tables only.
    Prevents costly repeated schema reflection across queries.
    """
    global _cached_sql_db
    if _cached_sql_db is None:
        _cached_sql_db = SQLDatabase.from_uri(
            settings.DATABASE_URL_SYNC,
            include_tables=OLIST_TABLES,
            sample_rows_in_table_info=2,
        )
    return _cached_sql_db


def get_sql_chain():
    """Create a LangChain SQL query chain for natural language → SQL."""
    db = get_sql_database()
    llm = get_chat_llm(temperature=0.0)
    return create_sql_query_chain(llm, db)


def clean_sql(raw: str) -> str:
    """Extracts clean executable SQL from LLM output, stripping markdown fences,
    prompts, and trailing commentary.
    """
    text = raw.strip()
    # 1. Look for ```sql ... ```
    fence = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    # 2. Look for SQLQuery:
    if "SQLQuery:" in text:
        text = text.split("SQLQuery:", 1)[1].strip()

    # 3. Strip trailing markers
    for marker in ["SQLResult:", "Answer:", "**SQLResult:**", "**Answer:**"]:
        if marker in text:
            text = text.split(marker, 1)[0].strip()

    # 4. Find SELECT or WITH statement
    match = re.search(r"\b(SELECT|WITH)\b[\s\S]*", text, re.IGNORECASE)
    if match:
        text = match.group(0).strip()

    # 5. Strip trailing backticks or quotes
    return text.rstrip(";` \n") + ";"


async def retrieve_structured(query: str) -> list[dict]:
    """
    Translate a natural language query into SQL, execute it, and return results.
    Uses Redis cache for identical SQL queries (PRD §5 Purpose 2).
    Returns list of dicts with keys: source_type, record_id, content, relevance_score.
    """
    try:
        # Generate SQL from natural language
        chain = get_sql_chain()
        raw_sql = await chain.ainvoke({"question": query})
        sql = clean_sql(raw_sql) if raw_sql else ""

        if not sql or not (sql.upper().startswith("SELECT") or sql.upper().startswith("WITH")):
            # Fallback: prompt LLM directly with table schema
            db = get_sql_database()
            llm = get_chat_llm(temperature=0.0)
            prompt = (
                f"You are a PostgreSQL expert. Given the database schema below, write a syntactically correct PostgreSQL query to answer the user's question.\n"
                f"Return ONLY executable SQL inside a ```sql``` code block.\n"
                f"Database Schema:\n{db.get_table_info()}\n\n"
                f"Question: {query}\n"
                f"SQL Query:"
            )
            resp = await llm.ainvoke(prompt)
            sql = clean_sql(resp.content)

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


def compute_delivery_delay(order_ids: list[str], session: Session) -> dict:
    """
    Computes deterministic average delivery delay in days for given order_ids.
    Calculation is performed purely in SQL:
      EXTRACT(EPOCH FROM (order_delivered_customer_date - order_estimated_delivery_date)) / 86400
    Only includes orders where delivered date is not null and delivered date > estimated date.
    Returns dict: {"avg_delay_days": float rounded to 1 decimal place}
    """
    if not order_ids:
        return {"avg_delay_days": 0.0}

    query = text("""
        SELECT AVG(EXTRACT(EPOCH FROM (order_delivered_customer_date - order_estimated_delivery_date)) / 86400.0)
        FROM olist_orders
        WHERE order_id = ANY(:order_ids)
          AND order_delivered_customer_date IS NOT NULL
          AND order_delivered_customer_date > order_estimated_delivery_date
    """)

    result = session.execute(query, {"order_ids": order_ids}).scalar()
    if result is None:
        return {"avg_delay_days": 0.0}

    return {"avg_delay_days": round(float(result), 1)}

