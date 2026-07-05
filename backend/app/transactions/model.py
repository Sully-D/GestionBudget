from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.tags.model import Tag


class TransactionTag(Base):
    __tablename__ = "transaction_tags"

    transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transactions.transaction_id"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.tag_id"), primary_key=True
    )


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.account_id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    payee: Mapped[str | None] = mapped_column(String, nullable=True)
    fitid: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[Tag]] = relationship(
        Tag, secondary=TransactionTag.__table__, order_by=Tag.tag_id, viewonly=True
    )
