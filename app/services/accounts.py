from sqlalchemy.orm import Session
from app.models import Account
from app.errors import AppError
from app.schemas import AccountCreate


def create_account(db: Session, data: AccountCreate) -> Account:
    acc = Account(name=data.name)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def get_account(db: Session, account_id: str) -> Account:
    acc = db.get(Account, account_id)
    if not acc:
        raise AppError(404, "ACCOUNT_NOT_FOUND", f"Account '{account_id}' not found")
    return acc
