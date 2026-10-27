import uuid
from tests.conftest import make_account, txn


def test_t1_credit(client):
    acc = make_account(client)
    r = txn(client, acc["id"], "credit", 100, "ref1")
    assert r.status_code == 201
    d = r.json()
    assert d["balance_after"] == "100.00"
    bal = client.get(f"/accounts/{acc['id']}/balance").json()
    assert bal["balance"] == "100.00"


def test_t2_sequence(client):
    acc = make_account(client)
    txn(client, acc["id"], "credit", 100, "r1")
    txn(client, acc["id"], "credit", 50, "r2")
    txn(client, acc["id"], "debit", 30, "r3")
    txn(client, acc["id"], "debit", 20, "r4")
    bal = client.get(f"/accounts/{acc['id']}/balance").json()
    assert bal["balance"] == "100.00"


def test_t3_insufficient_balance(client):
    acc = make_account(client)
    txn(client, acc["id"], "credit", 100, "r1")
    r = txn(client, acc["id"], "debit", 150, "r2")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSUFFICIENT_BALANCE"
    bal = client.get(f"/accounts/{acc['id']}/balance").json()
    assert bal["balance"] == "100.00"
    # no row stored
    hist = client.get(f"/accounts/{acc['id']}/transactions").json()
    assert hist["pagination"]["total_records"] == 1


def test_t4_exact_balance_debit(client):
    acc = make_account(client)
    txn(client, acc["id"], "credit", 100, "r1")
    r = txn(client, acc["id"], "debit", 100, "r2")
    assert r.status_code == 201
    assert r.json()["balance_after"] == "0.00"


def test_t5_invalid_type(client):
    acc = make_account(client)
    r = client.post("/transactions", json={
        "account_id": acc["id"], "type": "refund",
        "amount": 10, "reference_id": "r1", "description": "x"
    })
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_TRANSACTION_TYPE"


def test_t6_invalid_amount(client):
    acc = make_account(client)
    for bad in [0, -5, "abc", 10.555]:
        r = client.post("/transactions", json={
            "account_id": acc["id"], "type": "credit",
            "amount": bad, "reference_id": "r1", "description": "x"
        })
        assert r.status_code == 422, f"expected 422 for amount={bad}"
        assert r.json()["error"]["code"] == "INVALID_AMOUNT"


def test_t7_missing_fields(client):
    acc = make_account(client)
    # missing reference_id
    r = client.post("/transactions", json={"account_id": acc["id"], "type": "credit", "amount": 10, "description": "x"})
    assert r.status_code == 422
    # missing description
    r = client.post("/transactions", json={"account_id": acc["id"], "type": "credit", "amount": 10, "reference_id": "r1"})
    assert r.status_code == 422
    # blank reference_id
    r = client.post("/transactions", json={"account_id": acc["id"], "type": "credit", "amount": 10, "reference_id": "  ", "description": "x"})
    assert r.status_code == 422


def test_t7b_balance_unchanged_on_reject(client):
    acc = make_account(client)
    txn(client, acc["id"], "credit", 100, "r1")
    r = txn(client, acc["id"], "debit", 150, "r2")
    assert r.status_code == 422
    bal = client.get(f"/accounts/{acc['id']}/balance").json()
    assert bal["balance"] == "100.00"


def test_t8_unknown_account(client):
    r = txn(client, str(uuid.uuid4()), "credit", 10, "r1")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_t9_duplicate_same_account(client):
    acc = make_account(client)
    r1 = txn(client, acc["id"], "credit", 100, "ref-dup")
    assert r1.status_code == 201
    first_id = r1.json()["id"]

    r2 = txn(client, acc["id"], "credit", 100, "ref-dup")
    assert r2.status_code == 409
    body = r2.json()
    assert body["error"]["code"] == "DUPLICATE_TRANSACTION"
    assert body["error"]["details"]["existing_transaction"]["id"] == first_id

    # balance applied only once
    bal = client.get(f"/accounts/{acc['id']}/balance").json()
    assert bal["balance"] == "100.00"
    # only one row
    hist = client.get(f"/accounts/{acc['id']}/transactions").json()
    assert hist["pagination"]["total_records"] == 1


def test_t10_same_ref_different_accounts(client):
    a = make_account(client, "A")
    b = make_account(client, "B")
    r1 = txn(client, a["id"], "credit", 10, "shared-ref")
    r2 = txn(client, b["id"], "credit", 10, "shared-ref")
    assert r1.status_code == 201
    assert r2.status_code == 201


def test_t11_malformed_json(client):
    r = client.post("/transactions", content=b"{bad json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_t12_get_transaction(client):
    acc = make_account(client)
    r = txn(client, acc["id"], "credit", 50, "r1")
    txn_id = r.json()["id"]
    r2 = client.get(f"/transactions/{txn_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == txn_id

    r3 = client.get(f"/transactions/{uuid.uuid4()}")
    assert r3.status_code == 404
    assert r3.json()["error"]["code"] == "TRANSACTION_NOT_FOUND"
