# API Reference

Interactive docs: `http://localhost:8000/docs`  
OpenAPI schema: `http://localhost:8000/openapi.json`

## Error format (all errors use this shape)

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {}
  }
}
```

| HTTP | code | meaning |
|------|------|---------|
| 404 | `ACCOUNT_NOT_FOUND` | account UUID not found |
| 404 | `TRANSACTION_NOT_FOUND` | transaction UUID not found |
| 422 | `VALIDATION_ERROR` | missing/invalid field |
| 422 | `INVALID_TRANSACTION_TYPE` | type not credit or debit |
| 422 | `INVALID_AMOUNT` | amount <= 0, > 2 decimals, or non-numeric |
| 422 | `INSUFFICIENT_BALANCE` | debit exceeds balance |
| 422 | `SAME_ACCOUNT_TRANSFER` | from == to |
| 400 | `INVALID_PAGINATION` | page < 1, limit < 1 or > 100 |
| 409 | `DUPLICATE_TRANSACTION` | same reference_id on same account (or duplicate transfer ref) |
| 405 | `METHOD_NOT_ALLOWED` | PUT/PATCH/DELETE on transactions |
| 500 | `INTERNAL_ERROR` | unexpected server error |

---

## GET /health

Returns DB status.

**Response 200**
```json
{"status": "ok", "db": "ok"}
```

---

## POST /accounts

Create a new account. Balance always starts at 0. Extra fields (e.g. `balance`) are rejected.

**Request body**
```json
{"name": "Alice"}
```

| field | type | rules |
|-------|------|-------|
| `name` | string | required, non-blank, max 100 chars |

**Response 201**
```json
{"id": "uuid", "name": "Alice", "balance": "0.00", "created_at": "2026-10-27T10:00:00Z"}
```

---

## GET /accounts/{account_id}

**Response 200** — same shape as POST /accounts response.  
**Response 404** — `ACCOUNT_NOT_FOUND`

---

## GET /accounts/{account_id}/balance

**Response 200**
```json
{"account_id": "uuid", "balance": "150.00"}
```

---

## POST /transactions

Add a credit or debit transaction. Atomic with balance update.

**Request body**
```json
{
  "account_id": "uuid",
  "type": "credit",
  "amount": 100.50,
  "reference_id": "inv-001",
  "description": "Payment received"
}
```

| field | type | rules |
|-------|------|-------|
| `account_id` | UUID | must exist |
| `type` | string | `credit` or `debit` |
| `amount` | decimal | > 0, max 2 decimal places |
| `reference_id` | string | required, unique per account |
| `description` | string | required, non-blank, max 255 chars |

**Response 201**
```json
{
  "id": "uuid",
  "account_id": "uuid",
  "type": "credit",
  "amount": "100.50",
  "description": "Payment received",
  "reference_id": "inv-001",
  "transfer_id": null,
  "balance_after": "100.50",
  "created_at": "2026-10-27T10:00:00Z"
}
```

**Response 409** (duplicate)
```json
{
  "error": {
    "code": "DUPLICATE_TRANSACTION",
    "message": "Transaction with reference_id 'inv-001' already exists for this account",
    "details": {"existing_transaction": {...}}
  }
}
```

---

## GET /transactions/{transaction_id}

**Response 200** — same shape as POST /transactions response.  
**Response 404** — `TRANSACTION_NOT_FOUND`

---

## GET /accounts/{account_id}/transactions

Transaction history with optional filter and pagination.

**Query params**

| param | default | rules |
|-------|---------|-------|
| `type` | (both) | `credit` or `debit` |
| `page` | 1 | >= 1 |
| `limit` | 20 | 1–100 |

**Response 200**
```json
{
  "data": [...],
  "filters": {"type": "debit"},
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_records": 42,
    "total_pages": 3
  }
}
```

---

## POST /transfers

Transfer from one account to another. Atomic: debit on source + credit on destination or full rollback.

**Request body**
```json
{
  "from_account_id": "uuid",
  "to_account_id": "uuid",
  "amount": 30,
  "reference_id": "transfer-001",
  "description": "Rent"
}
```

| field | type | rules |
|-------|------|-------|
| `from_account_id` | UUID | must exist, must differ from `to_account_id` |
| `to_account_id` | UUID | must exist |
| `amount` | decimal | > 0, max 2 decimal places |
| `reference_id` | string | required, globally unique across transfers |
| `description` | string | optional, max 255 chars |

**Response 201**
```json
{
  "id": "uuid",
  "from_account_id": "uuid",
  "to_account_id": "uuid",
  "amount": "30.00",
  "reference_id": "transfer-001",
  "created_at": "2026-10-27T10:00:00Z",
  "from_balance_after": "70.00",
  "to_balance_after": "80.00"
}
```
