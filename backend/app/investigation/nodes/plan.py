from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.config import settings
from app.investigation.state import InvestigationState

plan_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an operational analyst. Given a business question,
decompose it into:
1. A list of SQL sub-queries to investigate the question against an e-commerce database.
2. A semantic search query for retrieving relevant documents.

The database contains these tables:
- olist_orders (order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date)
- olist_order_items (order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value)
- olist_customers (customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
- olist_sellers (seller_id, seller_zip_code_prefix, seller_city, seller_state)
- olist_products (product_id, product_category_name, product_weight_g, product_length_cm, product_height_cm, product_width_cm)
- olist_reviews (review_id, order_id, review_score, review_comment_title, review_comment_message)

Return a JSON object with exactly these keys:
- "sql_queries": list of natural language questions to be converted to SQL (max 5)
- "doc_query": a single semantic search query string for document retrieval

Example:
{{"sql_queries": ["How many orders were delivered late?", "Which seller states have the most delayed orders?"], "doc_query": "delivery delays logistics fulfillment"}}
"""),
    ("human", "{question}")
])


def get_llm():
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )


async def plan_investigation(state: InvestigationState) -> dict:
    """Decompose the question into SQL sub-queries and a document search query."""
    llm = get_llm()
    chain = plan_prompt | llm | JsonOutputParser()

    result = await chain.ainvoke({"question": state["question"]})

    return {
        "plan": result.get("sql_queries", []),
        "doc_query": result.get("doc_query", state["question"]),
        "current_node": "plan_investigation",
    }

