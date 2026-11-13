from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OlistOrder(Base):
    __tablename__ = "olist_orders"

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_status: Mapped[str | None] = mapped_column(Text)
    order_purchase_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_delivered_carrier_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_delivered_customer_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_estimated_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OlistCustomer(Base):
    __tablename__ = "olist_customers"

    customer_id: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_unique_id: Mapped[str | None] = mapped_column(Text)
    customer_zip_code_prefix: Mapped[str | None] = mapped_column(Text)
    customer_city: Mapped[str | None] = mapped_column(Text)
    customer_state: Mapped[str | None] = mapped_column(Text)


class OlistSeller(Base):
    __tablename__ = "olist_sellers"

    seller_id: Mapped[str] = mapped_column(Text, primary_key=True)
    seller_zip_code_prefix: Mapped[str | None] = mapped_column(Text)
    seller_city: Mapped[str | None] = mapped_column(Text)
    seller_state: Mapped[str | None] = mapped_column(Text)


class OlistProduct(Base):
    __tablename__ = "olist_products"

    product_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_category_name: Mapped[str | None] = mapped_column(Text)
    product_name_lenght: Mapped[int | None] = mapped_column(Integer)  # typo is in the original dataset
    product_description_lenght: Mapped[int | None] = mapped_column(Integer)  # typo is in the original dataset
    product_photos_qty: Mapped[int | None] = mapped_column(Integer)
    product_weight_g: Mapped[int | None] = mapped_column(Integer)
    product_length_cm: Mapped[int | None] = mapped_column(Integer)
    product_height_cm: Mapped[int | None] = mapped_column(Integer)
    product_width_cm: Mapped[int | None] = mapped_column(Integer)


class OlistOrderItem(Base):
    __tablename__ = "olist_order_items"

    order_id: Mapped[str] = mapped_column(Text, ForeignKey("olist_orders.order_id"), primary_key=True)
    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, ForeignKey("olist_products.product_id"), nullable=False)
    seller_id: Mapped[str] = mapped_column(Text, ForeignKey("olist_sellers.seller_id"), nullable=False)
    shipping_limit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    freight_value: Mapped[float | None] = mapped_column(Numeric(10, 2))


class OlistReview(Base):
    __tablename__ = "olist_reviews"

    review_id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("olist_orders.order_id"), nullable=False)
    review_score: Mapped[int | None] = mapped_column(Integer)
    review_comment_title: Mapped[str | None] = mapped_column(Text)
    review_comment_message: Mapped[str | None] = mapped_column(Text)
    review_creation_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_answer_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

