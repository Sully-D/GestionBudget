from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"
    __table_args__ = (
        CheckConstraint(
            "periodicity IN ('hebdomadaire', 'mensuelle', 'trimestrielle', 'annuelle')",
            name="ck_recurring_transactions_periodicity",
        ),
        CheckConstraint(
            "status IN ('confirmed', 'rejected')",
            name="ck_recurring_transactions_status",
        ),
    )

    recurring_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.account_id"), nullable=False
    )
    tag_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tags.tag_id"), nullable=True
    )
    signature: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    periodicity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class PlannedExpense(Base):
    __tablename__ = "planned_expenses"

    expense_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.account_id"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.tag_id"), nullable=False)
    series_id: Mapped[str | None] = mapped_column(String, nullable=True)
    period_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_periods: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
