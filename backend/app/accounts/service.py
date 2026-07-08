from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.core.period import period_for
from app.transactions.model import Transaction


def compute_balance(
    account: Account, db: Session, as_of_date: date | None = None
) -> Decimal:
    base = account.reference_balance if account.reference_balance is not None else Decimal("0.00")
    query = db.query(func.sum(Transaction.amount)).filter(
        Transaction.account_id == account.account_id
    )
    if account.reference_date is not None:
        query = query.filter(Transaction.date >= account.reference_date)
    if as_of_date is not None:
        query = query.filter(Transaction.date <= as_of_date)
    total = query.scalar() or Decimal("0.00")
    return base + total


def compute_period(
    account: Account, as_of_date: date | None = None
) -> tuple[date, date]:
    return period_for(account.start_day, as_of_date or date.today())
