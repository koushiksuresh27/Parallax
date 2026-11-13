import os
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.retrieval.structured import compute_delivery_delay
from app.models import OlistOrders, Base

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://parallax:changeme_in_production@localhost:5432/parallax_test"
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Clean tables before test run
    session.query(OlistOrders).delete()
    session.commit()

    # Seed the two specified test orders
    # order 1: 2021-01-10 vs 2021-01-07 -> 3 days delay
    order1 = OlistOrders(
        order_id="abc123",
        customer_id="c1",
        order_status="delivered",
        order_purchase_timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        order_approved_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
        order_delivered_customer_date=datetime(2021, 1, 10, tzinfo=timezone.utc),
        order_estimated_delivery_date=datetime(2021, 1, 7, tzinfo=timezone.utc),
    )

    # order 2: 2021-01-15 vs 2021-01-11 -> 4 days delay
    order2 = OlistOrders(
        order_id="def456",
        customer_id="c2",
        order_status="delivered",
        order_purchase_timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        order_approved_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
        order_delivered_customer_date=datetime(2021, 1, 15, tzinfo=timezone.utc),
        order_estimated_delivery_date=datetime(2021, 1, 11, tzinfo=timezone.utc),
    )

    session.add_all([order1, order2])
    session.commit()

    yield session

    session.rollback()
    session.close()


@pytest.mark.requires_db
def test_delivery_delay_is_deterministic(db_session):
    result = compute_delivery_delay(
        order_ids=["abc123", "def456"],
        session=db_session
    )
    assert result["avg_delay_days"] == 3.5


@pytest.mark.requires_db
def test_empty_order_list_returns_zero(db_session):
    result = compute_delivery_delay(order_ids=[], session=db_session)
    assert result["avg_delay_days"] == 0.0


@pytest.mark.requires_db
def test_no_delayed_orders_returns_zero(db_session):
    # Insert order where delivered_ts < estimated_delivery_ts (on-time)
    ontime_order = OlistOrders(
        order_id="ontime789",
        customer_id="c3",
        order_status="delivered",
        order_purchase_timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
        order_approved_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
        order_delivered_customer_date=datetime(2021, 1, 5, tzinfo=timezone.utc),
        order_estimated_delivery_date=datetime(2021, 1, 10, tzinfo=timezone.utc),
    )
    db_session.add(ontime_order)
    db_session.commit()

    result = compute_delivery_delay(order_ids=["ontime789"], session=db_session)
    assert result["avg_delay_days"] == 0.0
