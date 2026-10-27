from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text

from app.db import engine, Base
from app.errors import (
    AppError,
    app_error_handler,
    validation_error_handler,
    http_exception_handler,
    generic_exception_handler,
)
from app.routers import accounts, transactions, transfers

TRIGGER_DDL = """
CREATE OR REPLACE FUNCTION forbid_txn_change() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'transactions are immutable'; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS transactions_immutable ON transactions;
CREATE TRIGGER transactions_immutable
    BEFORE UPDATE OR DELETE ON transactions
    FOR EACH ROW EXECUTE FUNCTION forbid_txn_change();
"""

app = FastAPI(title="Ledger API", version="1.0.0")

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(transfers.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text(TRIGGER_DDL))
        conn.commit()


@app.get("/health", tags=["Health"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
