from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Revenue(Base):
    __tablename__ = "revenues"
    __table_args__ = (
        CheckConstraint("kind IN ('salaire', 'ponctuel')", name="ck_revenues_kind"),
    )

    revenue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.account_id"), nullable=False
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)


class BudgetTarget(Base):
    __tablename__ = "budget_targets"

    target_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.tag_id"), nullable=False)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.account_id"), nullable=False
    )
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
