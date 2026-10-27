import uuid
from decimal import Decimal
from sqlalchemy import (
    Column, String, Numeric, ForeignKey, CheckConstraint,
    UniqueConstraint, Index, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import relationship
from app.db import Base


def _uuid():
    return str(uuid.uuid4())


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_account_name_nonempty"),
        CheckConstraint("balance >= 0", name="ck_account_balance_nonneg"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    balance = Column(Numeric(18, 2), nullable=False, server_default=text("0"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    transactions = relationship("Transaction", back_populates="account", foreign_keys="Transaction.account_id")


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transfer_amount_pos"),
        CheckConstraint("from_account_id <> to_account_id", name="ck_transfer_diff_accounts"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    from_account_id = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    to_account_id = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    reference_id = Column(String(100), nullable=False, unique=True)
    description = Column(String(255))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    from_account = relationship("Account", foreign_keys=[from_account_id])
    to_account = relationship("Account", foreign_keys=[to_account_id])
    transactions = relationship("Transaction", back_populates="transfer")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type IN ('credit','debit')", name="ck_txn_type"),
        CheckConstraint("amount > 0", name="ck_txn_amount_pos"),
        CheckConstraint("length(trim(description)) > 0", name="ck_txn_desc_nonempty"),
        UniqueConstraint("account_id", "reference_id", name="uq_txn_account_ref"),
        Index("ix_txn_account_created", "account_id", "created_at", "id"),
        Index("ix_txn_account_type_created", "account_id", "type", "created_at", "id"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    type = Column(String(6), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    description = Column(String(255), nullable=False)
    reference_id = Column(String(100), nullable=False)
    transfer_id = Column(UUID(as_uuid=False), ForeignKey("transfers.id"), nullable=True)
    balance_after = Column(Numeric(18, 2), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    account = relationship("Account", back_populates="transactions", foreign_keys=[account_id])
    transfer = relationship("Transfer", back_populates="transactions")
