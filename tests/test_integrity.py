import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from tests.conftest import make_account, txn, test_engine, TestSession
from sqlalchemy import text


def test_i1_no_mutate_routes(client):
    from tests.conftest import make_account, txn
    acc = make_account(client)
    r = txn(client, acc["id"], "credit", 50, "r1")
    tid = r.json()["id"]
    for method in ["put", "patch", "delete"]:
        resp = getattr(client, method)(f"/transactions/{tid}")
        assert resp.status_code == 405, method
        assert resp.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_i2_trigger_blocks_update(client):
    acc = make_account(client)
    txn(client, acc["id"], "credit", 50, "r1")
    with TestSession() as db:
        with pytest.raises(Exception):
            db.execute(text("UPDATE transactions SET amount = 999 WHERE account_id = :id"), {"id": acc["id"]})
            db.commit()


def test_i3_concurrency_debits(client):
    """10 parallel debits of 20 on a 100-balance account. Exactly 5 succeed."""
    acc = make_account(client)
    txn(client, acc["id"], "credit", 100, "seed")

    from app.main import app
    results = []

    def do_debit(i):
        c = TestClient(app)
        return c.post("/transactions", json={
            "account_id": acc["id"], "type": "debit",
            "amount": 20, "reference_id": f"d{i}", "description": "concurrent"
        })

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(do_debit, i) for i in range(10)]
        results = [f.result() for f in as_completed(futures)]

    ok = [r for r in results if r.status_code == 201]
    fail = [r for r in results if r.status_code == 422]
    assert len(ok) == 5, f"expected 5 ok, got {len(ok)}"
    assert len(fail) == 5

    bal = client.get(f"/accounts/{acc['id']}/balance").json()
    assert bal["balance"] == "0.00"


def test_i4_concurrent_duplicates(client):
    """5 parallel identical requests. Exactly 1 succeeds, rest are 409."""
    acc = make_account(client)
    txn(client, acc["id"], "credit", 100, "seed")

    from app.main import app

    def do_debit():
        c = TestClient(app)
        return c.post("/transactions", json={
            "account_id": acc["id"], "type": "debit",
            "amount": 10, "reference_id": "same-ref", "description": "dup"
        })

    with ThreadPoolExecutor(max_workers=5) as ex:
        results = [ex.submit(do_debit) for _ in range(5)]
        results = [f.result() for f in as_completed(results)]

    ok = [r for r in results if r.status_code == 201]
    dup = [r for r in results if r.status_code == 409]
    assert len(ok) == 1
    assert len(dup) == 4

    bal = client.get(f"/accounts/{acc['id']}/balance").json()
    assert bal["balance"] == "90.00"


def test_i5_atomicity(client, monkeypatch):
    """If balance update fails, no transaction row is stored."""
    from fastapi.testclient import TestClient
    from app.main import app as fapp

    acc = make_account(client)
    txn(client, acc["id"], "credit", 100, "seed")

    import app.services.transactions as svc_mod

    def failing(db, data):
        raise RuntimeError("simulated failure mid-transaction")

    monkeypatch.setattr(svc_mod, "create_transaction", failing)

    noerr_client = TestClient(fapp, raise_server_exceptions=False)
    r = noerr_client.post("/transactions", json={
        "account_id": acc["id"], "type": "debit",
        "amount": 10, "reference_id": "fail-ref", "description": "test"
    })
    assert r.status_code == 500

    monkeypatch.undo()

    bal = client.get(f"/accounts/{acc['id']}/balance").json()
    assert bal["balance"] == "100.00"
    hist = client.get(f"/accounts/{acc['id']}/transactions").json()
    assert hist["pagination"]["total_records"] == 1


def test_i6_balance_invariant(client):
    acc = make_account(client)
    txn(client, acc["id"], "credit", 200, "r1")
    txn(client, acc["id"], "credit", 50, "r2")
    txn(client, acc["id"], "debit", 80, "r3")
    txn(client, acc["id"], "debit", 20, "r4")

    hist = client.get(f"/accounts/{acc['id']}/transactions").json()
    txns = hist["data"]
    credits = sum(float(t["amount"]) for t in txns if t["type"] == "credit")
    debits = sum(float(t["amount"]) for t in txns if t["type"] == "debit")
    expected = round(credits - debits, 2)

    bal = float(client.get(f"/accounts/{acc['id']}/balance").json()["balance"])
    assert bal == expected
