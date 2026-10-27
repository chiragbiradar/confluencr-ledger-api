import uuid
from tests.conftest import make_account


def test_a1_create_account(client):
    r = client.post("/accounts", json={"name": "Alice"})
    assert r.status_code == 201
    d = r.json()
    assert d["balance"] == "0.00"
    uuid.UUID(d["id"])  # valid UUID


def test_a2_name_missing(client):
    r = client.post("/accounts", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a2_name_blank(client):
    for name in ["", "   "]:
        r = client.post("/accounts", json={"name": name})
        assert r.status_code == 422, name
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a3_get_existing(client):
    acc = make_account(client, "Bob")
    r = client.get(f"/accounts/{acc['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Bob"


def test_a3_get_missing(client):
    r = client.get(f"/accounts/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_a4_invalid_uuid(client):
    r = client.get("/accounts/not-a-uuid")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a5_balance_field_rejected(client):
    r = client.post("/accounts", json={"name": "A", "balance": 500})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    # no account created
    r2 = client.post("/accounts", json={"name": "A"})
    assert r2.status_code == 201


def test_a6_balance_endpoint(client):
    acc = make_account(client)
    r = client.get(f"/accounts/{acc['id']}/balance")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"account_id", "balance"}
    assert body["account_id"] == acc["id"]
    assert body["balance"] == "0.00"


def test_a6_balance_missing(client):
    r = client.get(f"/accounts/{uuid.uuid4()}/balance")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}
