import pandas as pd
from sqlalchemy import text, String, Text, Integer, Numeric, DateTime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.olist import (
    OlistOrder,
    OlistCustomer,
    OlistSeller,
    OlistProduct,
    OlistOrderItem,
    OlistReview,
)

# Map filename patterns to ORM models
# The Kaggle CSVs are named like: olist_orders_dataset.csv
FILENAME_TO_MODEL = {
    "olist_orders": OlistOrder,
    "olist_customers": OlistCustomer,
    "olist_sellers": OlistSeller,
    "olist_products": OlistProduct,
    "olist_order_items": OlistOrderItem,
    "olist_order_reviews": OlistReview,
}


def match_olist_table(filename: str):
    """Match a filename to an Olist ORM model. Returns (model, table_key) or (None, None)."""
    name_lower = filename.lower()
    for key, model in FILENAME_TO_MODEL.items():
        if key in name_lower:
            return model, key
    return None, None


async def import_csv_to_olist(
    session: AsyncSession,
    file_path: str,
    filename: str,
) -> int:
    """
    Import a CSV file into the matching Olist table.
    Returns the number of rows inserted.
    Raises ValueError if the filename doesn't match any Olist table.
    """
    model, table_key = match_olist_table(filename)
    if model is None:
        raise ValueError(f"CSV filename '{filename}' does not match any Olist table pattern")

    df = pd.read_csv(file_path)

    # Match columns
    model_columns = {c.name: c for c in model.__table__.columns}
    csv_columns = set(df.columns)
    common_columns = set(model_columns.keys()) & csv_columns

    if not common_columns:
        raise ValueError(
            f"No matching columns between CSV ({csv_columns}) and table {model.__tablename__} ({set(model_columns.keys())})"
        )

    # Filter DataFrame to only matching columns
    df = df[list(common_columns)]

    # Cast string/text columns to str to prevent asyncpg type errors (e.g. zip codes read as ints)
    for col_name in common_columns:
        col = model_columns[col_name]
        if isinstance(col.type, (String, Text)):
            df[col_name] = df[col_name].apply(lambda x: str(x) if pd.notna(x) else None)
        elif isinstance(col.type, DateTime):
            df[col_name] = pd.to_datetime(df[col_name], errors="coerce").apply(
                lambda x: x.to_pydatetime() if pd.notna(x) else None
            )

    # Replace NaN/NaT with None for SQL compatibility
    df = df.where(df.notna(), None)

    table_name = model.__tablename__
    rows = df.to_dict(orient="records")

    if not rows:
        return 0

    # Clear existing data in the table before import (idempotent re-import)
    await session.execute(text(f"DELETE FROM {table_name}"))

    # Insert in batches of 1000
    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        await session.execute(model.__table__.insert(), batch)

    await session.commit()
    return len(rows)
