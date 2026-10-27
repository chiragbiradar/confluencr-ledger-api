import uuid
from tests.conftest import make_account, txn


def _seed_txns(client, acc_id, n):
    for i in range(n):
        txn(client, acc_id, "credit", 1, f"r{i}")


def test_p1_pagination_basic(client):
    acc = make_account(client)
    _seed_txns(client, acc["id"], 25)
    r = client.get(f"/accounts/{acc['id']}/transactions?page=1&limit=10")
    assert r.status_code == 200
    d = r.json()
    assert len(d["data"]) == 10
    p = d["pagination"]
    assert p["page"] == 1
    assert p["limit"] == 10
    assert p["total_records"] == 25
    assert p["total_pages"] == 3


def test_p2_page3(client):
    acc = make_account(client)
    _seed_txns(client, acc["id"], 25)
    r = client.get(f"/accounts/{acc['id']}/transactions?page=3&limit=10")
    assert len(r.json()["data"]) == 5


def test_p3_past_end(client):
    acc = make_account(client)
    _seed_txns(client, acc["id"], 25)
    r = client.get(f"/accounts/{acc['id']}/transactions?page=4&limit=10")
    d = r.json()
    assert d["data"] == []
    assert d["pagination"]["total_records"] == 25
    assert d["pagination"]["total_pages"] == 3


def test_p4_latest_first(client):
    acc = make_account(client)
    _seed_txns(client, acc["id"], 5)
    r = client.get(f"/accounts/{acc['id']}/transactions")
    rows = r.json()["data"]
    dates = [row["created_at"] for row in rows]
    assert dates == sorted(dates, reverse=True)


def test_p5_defaults(client):
    acc = make_account(client)
    _seed_txns(client, acc["id"], 5)
    r = client.get(f"/accounts/{acc['id']}/transactions")
    p = r.json()["pagination"]
    assert p["page"] == 1
    assert p["limit"] == 20


def test_p6_invalid_pagination(client):
    acc = make_account(client)
    for params in ["page=0", "limit=0", "limit=101", "page=abc"]:
        r = client.get(f"/accounts/{acc['id']}/transactions?{params}")
        assert r.status_code in (400, 422), params
        assert r.json()["error"]["code"] == "INVALID_PAGINATION"


def test_p7_unknown_account(client):
    r = client.get(f"/accounts/{uuid.uuid4()}/transactions")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_p7_no_txns(client):
    acc = make_account(client)
    r = client.get(f"/accounts/{acc['id']}/transactions")
    d = r.json()
    assert d["data"] == []
    assert d["pagination"]["total_records"] == 0
    assert d["pagination"]["total_pages"] == 0


def test_p8_type_filter(client):
    acc = make_account(client)
    for i in range(6):
        txn(client, acc["id"], "credit", 10, f"c{i}")
    txn(client, acc["id"], "credit", 60, "seed")  # so we have balance for debits
    # re-seed balance
    for i in range(4):
        txn(client, acc["id"], "debit", 5, f"d{i}")

    r = client.get(f"/accounts/{acc['id']}/transactions?type=credit")
    d = r.json()
    assert d["pagination"]["total_records"] == 7  # 6 + seed
    assert all(t["type"] == "credit" for t in d["data"])

    r2 = client.get(f"/accounts/{acc['id']}/transactions?type=debit")
    d2 = r2.json()
    assert d2["pagination"]["total_records"] == 4
    assert all(t["type"] == "debit" for t in d2["data"])


def test_p9_no_type_filter_returns_both(client):
    acc = make_account(client)
    txn(client, acc["id"], "credit", 100, "c1")
    txn(client, acc["id"], "debit", 10, "d1")
    r = client.get(f"/accounts/{acc['id']}/transactions")
    assert r.json()["pagination"]["total_records"] == 2


def test_p10_invalid_type_filter(client):
    acc = make_account(client)
    r = client.get(f"/accounts/{acc['id']}/transactions?type=refund")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_TRANSACTION_TYPE"


def test_p10_filter_and_pagination(client):
    acc = make_account(client)
    for i in range(6):
        txn(client, acc["id"], "credit", 10, f"c{i}")
    r = client.get(f"/accounts/{acc['id']}/transactions?type=credit&limit=4&page=2")
    d = r.json()
    assert len(d["data"]) == 2
    assert d["pagination"]["total_pages"] == 2
