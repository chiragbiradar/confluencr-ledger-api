from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import TransactionCreate, TransactionOut
from app.services import transactions as svc

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", status_code=201, response_model=TransactionOut)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    txn = svc.create_transaction(db, data)
    return TransactionOut.from_orm(txn)


@router.get("/{txn_id}", response_model=TransactionOut)
def get_transaction(txn_id: UUID, db: Session = Depends(get_db)):
    txn = svc.get_transaction(db, str(txn_id))
    return TransactionOut.from_orm(txn)
