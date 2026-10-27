# Assumptions

1. Single currency (INR). Amounts allow up to 2 decimal places. Max is 999,999,999,999.99.
2. Accounts start at balance 0. Money only enters through credit transactions.
3. Rejected transactions (insufficient balance, validation errors) are **not stored**. The request fails and nothing is persisted.
4. `reference_id` is unique **per account**. A repeat with the same `(account_id, reference_id)` returns `409 DUPLICATE_TRANSACTION`, and the response includes the existing transaction. It is never applied twice. This makes client retries safe (idempotent).
5. Balance can never go negative. Enforced in code **and** by a DB `CHECK (balance >= 0)` constraint.
6. IDs are UUIDs. Timestamps are UTC ISO-8601.
7. Pagination: `page >= 1` (default 1), `limit` between 1 and 100 (default 20). Asking for a page past the end returns an empty `data` list with correct totals.
8. No authentication. Out of scope for the brief.
9. Transfer: `from_account_id != to_account_id`. One transfer creates two linked transactions — a debit on the source and a credit on the destination — sharing `transfer_id`. The transfer's `reference_id` is unique across all transfers.
10. The account name is not unique (two accounts can share a name).
11. `description` is required and must not be blank. Max 255 characters.
12. Unknown fields in request bodies are rejected with 422 (`extra="forbid"`). This is how "the client can't set the initial balance" is enforced: `POST /accounts {"name":"A","balance":500}` returns 422, not a silent ignore.
13. An invalid `type` filter on the history endpoint (e.g. `?type=refund`) returns 422 INVALID_TRANSACTION_TYPE.
14. Money is serialized as **strings** with 2 decimal places (e.g. `"100.50"`) to avoid float rounding in JSON clients.
15. Alembic migrations are omitted for this take-home. In production, schema changes would go through Alembic.
