from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("start_day >= 1 AND start_day <= 28", name="ck_accounts_start_day_range"),
    )

    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    is_common: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_day: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # NB% de charges convenu (Récap Budget Couple, Compte Commun uniquement) — persisté
    # tel quel, rechargé à chaque visite (cf. spec-recap-budget-couple-dashboard-commun.md).
    couple_charges_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
