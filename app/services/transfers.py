from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import Account, Transfer, Transaction
from app.errors import AppError
from app.schemas import TransferCreate, TransferOut, TransactionOut


def create_transfer(db: Session, data: TransferCreate) -> dict:
    from_id = str(data.from_account_id)
    to_id = str(data.to_account_id)

    if from_id == to_id:
        raise AppError(422, "SAME_ACCOUNT_TRANSFER", "Source and destination accounts must differ")

    # Pre-check duplicate transfer reference
    existing_transfer = db.execute(
        select(Transfer).where(Transfer.reference_id == data.reference_id)
    ).scalar_one_or_none()
    if existing_transfer:
        raise AppError(409, "DUPLICATE_TRANSACTION", f"Transfer with reference_id '{data.reference_id}' already exists")

    # Lock both accounts in id order to avoid deadlock
    ids_sorted = sorted([from_id, to_id])
    with db.begin_nested():
        locked = db.execute(
            select(Account)
            .where(Account.id.in_(ids_sorted))
            .order_by(Account.id)
            .with_for_update()
        ).scalars().all()

        by_id = {a.id: a for a in locked}
        if from_id not in by_id:
            raise AppError(404, "ACCOUNT_NOT_FOUND", f"Account '{from_id}' not found")
        if to_id not in by_id:
            raise AppError(404, "ACCOUNT_NOT_FOUND", f"Account '{to_id}' not found")

        src = by_id[from_id]
        dst = by_id[to_id]

        if src.balance < data.amount:
            raise AppError(
                422,
                "INSUFFICIENT_BALANCE",
                f"Account balance {src.balance:.2f} is less than transfer amount {data.amount:.2f}",
            )

        transfer = Transfer(
            from_account_id=from_id,
            to_account_id=to_id,
            amount=data.amount,
            reference_id=data.reference_id,
            description=data.description,
        )
        db.add(transfer)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise AppError(409, "DUPLICATE_TRANSACTION", f"Transfer with reference_id '{data.reference_id}' already exists")

        from_new = src.balance - data.amount
        to_new = dst.balance + data.amount

        debit_leg = Transaction(
            account_id=from_id,
            type="debit",
            amount=data.amount,
            description=data.description or f"Transfer to {to_id}",
            reference_id=data.reference_id,
            transfer_id=transfer.id,
            balance_after=from_new,
        )
        credit_leg = Transaction(
            account_id=to_id,
            type="credit",
            amount=data.amount,
            description=data.description or f"Transfer from {from_id}",
            reference_id=data.reference_id,
            transfer_id=transfer.id,
            balance_after=to_new,
        )
        db.add(debit_leg)
        db.add(credit_leg)
        db.flush()

        src.balance = from_new
        dst.balance = to_new

    db.commit()
    db.refresh(transfer)

    return {
        "id": transfer.id,
        "from_account_id": transfer.from_account_id,
        "to_account_id": transfer.to_account_id,
        "amount": f"{transfer.amount:.2f}",
        "reference_id": transfer.reference_id,
        "created_at": transfer.created_at,
        "from_balance_after": f"{from_new:.2f}",
        "to_balance_after": f"{to_new:.2f}",
    }
