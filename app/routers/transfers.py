from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import TransferCreate, TransferOut
from app.services import transfers as svc

router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post("", status_code=201, response_model=TransferOut)
def create_transfer(data: TransferCreate, db: Session = Depends(get_db)):
    result = svc.create_transfer(db, data)
    return TransferOut(**result)
