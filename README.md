# Ledger API

A transaction ledger system: create accounts, credit/debit them, transfer funds between them. Built as a Confluencr take-home.

## Tech stack

| | Why |
|---|---|
| **FastAPI** | Auto-generated OpenAPI docs, Pydantic v2 validation, fast to build |
| **PostgreSQL 16** | ACID transactions, `SELECT … FOR UPDATE`, `CHECK` constraints, `UNIQUE` |
| **SQLAlchemy 2 (sync)** | Easy-to-read transaction logic; sync keeps the locking flow explicit |
| **pytest + httpx TestClient** | Tests run against a real Postgres test DB (not SQLite — it lacks `FOR UPDATE`) |

## Run locally

```bash
cp .env.example .env
docker compose up -d          # starts postgres:16 on port 5432
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API docs.

## Run tests

```bash
pytest -q
```

Tests hit a real Postgres test DB (`ledger_test`). Each test truncates all tables before running.

## Quick demo

```bash
# Create two accounts
A=$(curl -s -X POST localhost:8000/accounts -H 'Content-Type: application/json' \
  -d '{"name":"Alice"}' | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
B=$(curl -s -X POST localhost:8000/accounts -H 'Content-Type: application/json' \
  -d '{"name":"Bob"}' | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Credit Alice 100, Bob 50
curl -s -X POST localhost:8000/transactions \
  -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$A\",\"type\":\"credit\",\"amount\":100,\"reference_id\":\"r1\",\"description\":\"Salary\"}"

curl -s -X POST localhost:8000/transactions \
  -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$B\",\"type\":\"credit\",\"amount\":50,\"reference_id\":\"r1\",\"description\":\"Salary\"}"

# Transfer 30 from Alice to Bob
curl -s -X POST localhost:8000/transfers \
  -H 'Content-Type: application/json' \
  -d "{\"from_account_id\":\"$A\",\"to_account_id\":\"$B\",\"amount\":30,\"reference_id\":\"tr1\",\"description\":\"Rent\"}"

# Check balances (Alice=70, Bob=80)
curl -s localhost:8000/accounts/$A/balance
curl -s localhost:8000/accounts/$B/balance

# Insufficient balance (rejected)
curl -s -X POST localhost:8000/transactions \
  -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$A\",\"type\":\"debit\",\"amount\":999,\"reference_id\":\"r2\",\"description\":\"Too much\"}"
```

## Design decisions

**Atomicity** — Every mutation (`POST /transactions`, `POST /transfers`) runs inside a single DB transaction via `session.begin_nested()` + `session.commit()`. Any failure (constraint violation, runtime error) rolls back everything. No partial state ever persists.

**Concurrency** — `SELECT … FOR UPDATE` locks the account row before reading the balance. Two concurrent debits on the same account wait for each other, so only one can pass the balance check. Transfers lock both account rows sorted by UUID to prevent A→B / B→A deadlocks.

**Two-layer integrity** — Business rules are checked in Python (friendly error messages), then enforced again at the DB level (`CHECK balance >= 0`, `CHECK amount > 0`, `CHECK type IN ('credit','debit')`, `UNIQUE(account_id, reference_id)`). The DB constraint is the last line of defense against races.

**Immutability** — No PUT/PATCH/DELETE routes on transactions (FastAPI returns 405). A PostgreSQL trigger (`BEFORE UPDATE OR DELETE`) raises an exception if a transaction row is ever touched directly.

**Money as strings** — Amounts are stored as `NUMERIC(18,2)` and serialized as strings (e.g. `"100.50"`). This prevents JSON float rounding in clients that parse `100.10` as `100.09999…`.

**`balance_after` per transaction** — Stored alongside each transaction for instant auditing. The invariant `account.balance == SUM(credits) - SUM(debits)` can be verified with a single SQL query.

## What I'd add for production

- **Alembic** for schema migrations (mentioned in code; omitted here for brevity)
- **Auth** (JWT / API keys) — explicitly out of scope for this brief
- **Structured logging** (JSON) + metrics (Prometheus)
- **Keyset pagination** for very large transaction histories
- **Outbox / event table** for publishing balance-change events to a message bus
- **Rate limiting** on the transaction endpoint
- **Idempotency keys** with stored responses (the current `reference_id` is halfway there)
- **Deploy**: Render (backend) + Supabase Postgres, with `DATABASE_URL` as an env var

## AI usage

Built with Claude Code. I (Chirag) designed the schema and concurrency approach, reviewed every line, and ran all the tests myself. Confluencr values how you check AI output — that review process is exactly what happened here.
