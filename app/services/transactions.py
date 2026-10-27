import math
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from app.models import Account, Transaction
from app.errors import AppError
from app.schemas import TransactionCreate, TransactionOut


def create_transaction(db: Session, data: TransactionCreate) -> Transaction:
    account_id = str(data.account_id)

    # Pre-check duplicate (friendly error path; UNIQUE constraint is the real guard)
    existing = db.execute(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.reference_id == data.reference_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise AppError(
            409,
            "DUPLICATE_TRANSACTION",
            f"Transaction with reference_id '{data.reference_id}' already exists for this account",
            {"existing_transaction": TransactionOut.from_orm(existing).model_dump(mode="json")},
        )

    try:
        with db.begin_nested():
            # Lock the account row
            account = db.execute(
                select(Account).where(Account.id == account_id).with_for_update()
            ).scalar_one_or_none()
            if not account:
                raise AppError(404, "ACCOUNT_NOT_FOUND", f"Account '{account_id}' not found")

            if data.type == "debit":
                if account.balance < data.amount:
                    raise AppError(
                        422,
                        "INSUFFICIENT_BALANCE",
                        f"Account balance {account.balance:.2f} is less than debit amount {data.amount:.2f}",
                    )
                new_balance = account.balance - data.amount
            else:
                new_balance = account.balance + data.amount

            txn = Transaction(
                account_id=account_id,
                type=data.type,
                amount=data.amount,
                description=data.description,
                reference_id=data.reference_id,
                balance_after=new_balance,
            )
            db.add(txn)
            db.flush()
            account.balance = new_balance
    except IntegrityError:
        # SAVEPOINT already rolled back; look up the winning transaction
        existing = db.execute(
            select(Transaction).where(
                Transaction.account_id == account_id,
                Transaction.reference_id == data.reference_id,
            )
        ).scalar_one_or_none()
        raise AppError(
            409,
            "DUPLICATE_TRANSACTION",
            f"Transaction with reference_id '{data.reference_id}' already exists for this account",
            {"existing_transaction": TransactionOut.from_orm(existing).model_dump(mode="json") if existing else {}},
        )

    db.commit()
    db.refresh(txn)
    return txn


def get_transaction(db: Session, txn_id: str) -> Transaction:
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise AppError(404, "TRANSACTION_NOT_FOUND", f"Transaction '{txn_id}' not found")
    return txn


def list_transactions(db: Session, account_id: str, txn_type: str | None, page: int, limit: int) -> dict:
    from app.services.accounts import get_account
    get_account(db, account_id)  # 404 if missing

    where = [Transaction.account_id == account_id]
    if txn_type:
        where.append(Transaction.type == txn_type)

    total = db.execute(select(func.count()).select_from(Transaction).where(*where)).scalar()
    total_pages = math.ceil(total / limit) if total > 0 else 0

    rows = db.execute(
        select(Transaction)
        .where(*where)
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(limit)
        .offset((page - 1) * limit)
    ).scalars().all()

    return {
        "data": rows,
        "filters": {"type": txn_type} if txn_type else {},
        "pagination": {"page": page, "limit": limit, "total_records": total, "total_pages": total_pages},
    }
