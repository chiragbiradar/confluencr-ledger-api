import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from tests.conftest import make_account, txn


def transfer(client, from_id, to_id, amount, ref, description=None):
    body = {"from_account_id": from_id, "to_account_id": to_id,
            "amount": amount, "reference_id": ref}
    if description:
        body["description"] = description
    return client.post("/transfers", json=body)


def test_x1_basic_transfer(client):
    a = make_account(client, "A")
    b = make_account(client, "B")
    txn(client, a["id"], "credit", 100, "seed-a")
    txn(client, b["id"], "credit", 50, "seed-b")

    r = transfer(client, a["id"], b["id"], 30, "tr1")
    assert r.status_code == 201
    d = r.json()
    assert d["from_balance_after"] == "70.00"
    assert d["to_balance_after"] == "80.00"

    assert client.get(f"/accounts/{a['id']}/balance").json()["balance"] == "70.00"
    assert client.get(f"/accounts/{b['id']}/balance").json()["balance"] == "80.00"


def test_x2_insufficient_balance(client):
    a = make_account(client, "A")
    b = make_account(client, "B")
    txn(client, a["id"], "credit", 10, "s1")

    r = transfer(client, a["id"], b["id"], 20, "tr-fail")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSUFFICIENT_BALANCE"
    assert client.get(f"/accounts/{a['id']}/balance").json()["balance"] == "10.00"
    assert client.get(f"/accounts/{b['id']}/balance").json()["balance"] == "0.00"


def test_x3_missing_account(client):
    a = make_account(client)
    r = transfer(client, a["id"], str(uuid.uuid4()), 10, "tr-miss")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_x4_same_account(client):
    a = make_account(client)
    r = transfer(client, a["id"], a["id"], 10, "tr-same")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SAME_ACCOUNT_TRANSFER"


def test_x5_duplicate_transfer(client):
    a = make_account(client, "A")
    b = make_account(client, "B")
    txn(client, a["id"], "credit", 100, "seed")

    transfer(client, a["id"], b["id"], 10, "tr-dup")
    r2 = transfer(client, a["id"], b["id"], 10, "tr-dup")
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "DUPLICATE_TRANSACTION"

    # applied once
    assert client.get(f"/accounts/{a['id']}/balance").json()["balance"] == "90.00"
    assert client.get(f"/accounts/{b['id']}/balance").json()["balance"] == "10.00"


def test_x6_rollback_on_failure(client, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app as fapp

    a = make_account(client, "A")
    b = make_account(client, "B")
    txn(client, a["id"], "credit", 100, "seed")

    import app.services.transfers as tr_svc

    def failing(db, data):
        raise RuntimeError("simulated credit leg failure")

    monkeypatch.setattr(tr_svc, "create_transfer", failing)

    noerr_client = TestClient(fapp, raise_server_exceptions=False)
    r = noerr_client.post("/transfers", json={
        "from_account_id": a["id"], "to_account_id": b["id"],
        "amount": 30, "reference_id": "tr-fail"
    })
    assert r.status_code == 500

    monkeypatch.undo()

    assert client.get(f"/accounts/{a['id']}/balance").json()["balance"] == "100.00"
    assert client.get(f"/accounts/{b['id']}/balance").json()["balance"] == "0.00"


def test_x7_deadlock_safety(client):
    """A->B and B->A concurrent transfers should all succeed without deadlock."""
    a = make_account(client, "A")
    b = make_account(client, "B")
    txn(client, a["id"], "credit", 100, "sa")
    txn(client, b["id"], "credit", 100, "sb")

    from app.main import app as fapp

    def do_transfer(i, from_id, to_id, ref):
        c = TestClient(fapp)
        return c.post("/transfers", json={
            "from_account_id": from_id, "to_account_id": to_id,
            "amount": 1, "reference_id": ref
        })

    futures = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        for i in range(10):
            futures.append(ex.submit(do_transfer, i, a["id"], b["id"], f"ab-{i}"))
            futures.append(ex.submit(do_transfer, i, b["id"], a["id"], f"ba-{i}"))
        results = [f.result() for f in as_completed(futures)]

    # All should succeed
    for r in results:
        assert r.status_code == 201, r.text

    bal_a = float(client.get(f"/accounts/{a['id']}/balance").json()["balance"])
    bal_b = float(client.get(f"/accounts/{b['id']}/balance").json()["balance"])
    assert round(bal_a + bal_b, 2) == 200.0


def test_x9_transfer_ref_matches_existing_transaction(client):
    """reference_id used in a prior transaction → transfer returns 409, not 500."""
    a = make_account(client, "A")
    b = make_account(client, "B")
    txn(client, a["id"], "credit", 100, "seed")
    # Use same reference_id for a direct transaction on a, then try to transfer
    txn(client, a["id"], "credit", 10, "reused-ref")
    r = transfer(client, a["id"], b["id"], 5, "reused-ref")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_TRANSACTION"


def test_x10_blank_description_returns_422(client):
    """Blank description on transfer request → 422 VALIDATION_ERROR, not 500."""
    a = make_account(client, "A")
    b = make_account(client, "B")
    txn(client, a["id"], "credit", 100, "seed")
    r = client.post("/transfers", json={
        "from_account_id": a["id"], "to_account_id": b["id"],
        "amount": 10, "reference_id": "tr-blank-desc", "description": "   "
    })
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_x8_legs_in_history(client):
    a = make_account(client, "A")
    b = make_account(client, "B")
    txn(client, a["id"], "credit", 100, "seed")

    r = transfer(client, a["id"], b["id"], 30, "tr-legs")
    transfer_id = r.json()["id"]

    hist_a = client.get(f"/accounts/{a['id']}/transactions").json()["data"]
    hist_b = client.get(f"/accounts/{b['id']}/transactions").json()["data"]

    a_transfer_txns = [t for t in hist_a if t["transfer_id"] == transfer_id]
    b_transfer_txns = [t for t in hist_b if t["transfer_id"] == transfer_id]

    assert len(a_transfer_txns) == 1
    assert a_transfer_txns[0]["type"] == "debit"
    assert len(b_transfer_txns) == 1
    assert b_transfer_txns[0]["type"] == "credit"
