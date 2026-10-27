import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ledger:ledger@localhost:5432/ledger_test")
os.environ["DATABASE_URL"] = "postgresql+psycopg://ledger:ledger@localhost:5432/ledger_test"

from app.main import app, TRIGGER_DDL
from app.db import Base, get_db

TEST_URL = "postgresql+psycopg://ledger:ledger@localhost:5432/ledger_test"

test_engine = create_engine(TEST_URL, pool_pre_ping=True)
TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        conn.execute(text(TRIGGER_DDL))
        conn.commit()


@pytest.fixture(autouse=True)
def truncate_tables():
    yield
    with test_engine.connect() as conn:
        conn.execute(text("TRUNCATE transactions, transfers, accounts RESTART IDENTITY CASCADE"))
        conn.commit()


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


# Helpers
def make_account(client, name="Alice"):
    r = client.post("/accounts", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def txn(client, account_id, type_, amount, ref, description="test"):
    return client.post("/transactions", json={
        "account_id": account_id,
        "type": type_,
        "amount": amount,
        "reference_id": ref,
        "description": description,
    })
