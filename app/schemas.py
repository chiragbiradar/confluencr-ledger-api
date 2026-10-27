from __future__ import annotations
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _money(v) -> str:
    return f"{Decimal(str(v)):.2f}"


# ── Accounts ──────────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()


class AccountOut(BaseModel):
    id: str
    name: str
    balance: str
    created_at: datetime

    @classmethod
    def from_orm(cls, obj) -> "AccountOut":
        return cls(id=obj.id, name=obj.name, balance=_money(obj.balance), created_at=obj.created_at)


class BalanceOut(BaseModel):
    account_id: str
    balance: str

    @classmethod
    def from_orm(cls, obj) -> "BalanceOut":
        return cls(account_id=obj.id, balance=_money(obj.balance))


# ── Transactions ───────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID
    type: Literal["credit", "debit"]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    description: str = Field(min_length=1, max_length=255)
    reference_id: str = Field(min_length=1, max_length=100)

    @field_validator("description", "reference_id")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        try:
            d = Decimal(str(v))
        except Exception:
            raise ValueError("amount must be a valid number")
        if d != d:  # NaN
            raise ValueError("amount must not be NaN")
        if not d.is_finite():
            raise ValueError("amount must be finite")
        return d


class TransactionOut(BaseModel):
    id: str
    account_id: str
    type: str
    amount: str
    description: str
    reference_id: str
    transfer_id: Optional[str]
    balance_after: str
    created_at: datetime

    @classmethod
    def from_orm(cls, obj) -> "TransactionOut":
        return cls(
            id=obj.id,
            account_id=obj.account_id,
            type=obj.type,
            amount=_money(obj.amount),
            description=obj.description,
            reference_id=obj.reference_id,
            transfer_id=obj.transfer_id,
            balance_after=_money(obj.balance_after),
            created_at=obj.created_at,
        )


class TransactionListOut(BaseModel):
    data: list[TransactionOut]
    filters: dict
    pagination: dict


# ── Transfers ─────────────────────────────────────────────────────────────────

class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reference_id: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=255)

    @field_validator("reference_id")
    @classmethod
    def ref_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        try:
            d = Decimal(str(v))
        except Exception:
            raise ValueError("amount must be a valid number")
        if not d.is_finite():
            raise ValueError("amount must be finite")
        return d


class TransferOut(BaseModel):
    id: str
    from_account_id: str
    to_account_id: str
    amount: str
    reference_id: str
    created_at: datetime
    from_balance_after: str
    to_balance_after: str
