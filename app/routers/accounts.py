from uuid import UUID
from typing import Literal, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import AccountCreate, AccountOut, BalanceOut, TransactionOut, TransactionListOut
from app.services import accounts as svc
from app.services import transactions as txn_svc
from app.errors import AppError

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("", status_code=201, response_model=AccountOut)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    acc = svc.create_account(db, data)
    return AccountOut.from_orm(acc)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: UUID, db: Session = Depends(get_db)):
    acc = svc.get_account(db, str(account_id))
    return AccountOut.from_orm(acc)


@router.get("/{account_id}/balance", response_model=BalanceOut)
def get_balance(account_id: UUID, db: Session = Depends(get_db)):
    acc = svc.get_account(db, str(account_id))
    return BalanceOut.from_orm(acc)


@router.get("/{account_id}/transactions", response_model=TransactionListOut)
def list_transactions(
    account_id: UUID,
    type: Optional[Literal["credit", "debit"]] = Query(default=None),
    page: int = Query(default=1),
    limit: int = Query(default=20),
    db: Session = Depends(get_db),
):
    if page < 1 or limit < 1 or limit > 100:
        raise AppError(400, "INVALID_PAGINATION", "page >= 1, limit 1-100")
    result = txn_svc.list_transactions(db, str(account_id), type, page, limit)
    return TransactionListOut(
        data=[TransactionOut.from_orm(t) for t in result["data"]],
        filters=result["filters"],
        pagination=result["pagination"],
    )
