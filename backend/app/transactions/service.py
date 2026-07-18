from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.accounts.model import Account
from app.accounts.service import compute_period
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag
from app.transactions.schema import TransactionCreate, TransactionUpdate


def list_transactions(
    account_id: int, reference_date: date | None, db: Session
) -> tuple[date, date, list[Transaction]]:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")

    period_start, period_end = compute_period(account, reference_date)
    transactions = (
        db.query(Transaction)
        .options(selectinload(Transaction.tags))
        .filter(
            Transaction.account_id == account_id,
            Transaction.date >= period_start,
            Transaction.date <= period_end,
        )
        .order_by(Transaction.date.desc(), Transaction.transaction_id.desc())
        .all()
    )
    return period_start, period_end, transactions


def _contains_pattern(term: str) -> str:
    # Échappe les caractères spéciaux LIKE (`%`, `_`) pour que la recherche
    # "contient" reste une correspondance littérale, pas un motif joker.
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_transactions(
    account_id: int,
    *,
    label: str | None,
    payee: str | None,
    amount: Decimal | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    date_exact: date | None,
    date_from: date | None,
    date_to: date | None,
    tag_ids: list[int] | None,
    db: Session,
) -> list[Transaction]:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")

    query = db.query(Transaction).options(selectinload(Transaction.tags)).filter(
        Transaction.account_id == account_id
    )

    label = label.strip() if label else None
    payee = payee.strip() if payee else None
    if label:
        query = query.filter(
            func.lower(Transaction.label).like(
                func.lower(_contains_pattern(label)), escape="\\"
            )
        )
    if payee:
        query = query.filter(
            func.lower(Transaction.payee).like(
                func.lower(_contains_pattern(payee)), escape="\\"
            )
        )
    if amount is not None:
        query = query.filter(Transaction.amount == amount)
    if amount_min is not None:
        query = query.filter(Transaction.amount >= amount_min)
    if amount_max is not None:
        query = query.filter(Transaction.amount <= amount_max)
    if date_exact is not None:
        query = query.filter(Transaction.date == date_exact)
    if date_from is not None:
        query = query.filter(Transaction.date >= date_from)
    if date_to is not None:
        query = query.filter(Transaction.date <= date_to)
    if tag_ids:
        query = query.filter(
            Transaction.transaction_id.in_(
                select(TransactionTag.transaction_id).where(
                    TransactionTag.tag_id.in_(tag_ids)
                )
            )
        )

    return (
        query.order_by(Transaction.date.desc(), Transaction.transaction_id.desc())
        .all()
    )


def create_transaction(payload: TransactionCreate, db: Session) -> Transaction:
    account = db.get(Account, payload.account_id)
    if account is None:
        raise HTTPException(
            status_code=404, detail=f"Compte {payload.account_id} introuvable"
        )

    transaction = Transaction(
        account_id=payload.account_id,
        date=payload.date,
        amount=payload.amount,
        label=payload.label,
        payee=payload.payee,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_transaction(transaction_id: int, db: Session) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=404, detail=f"Transaction {transaction_id} introuvable"
        )
    return transaction


def update_transaction(
    transaction_id: int, payload: TransactionUpdate, db: Session
) -> Transaction:
    transaction = get_transaction(transaction_id, db)
    transaction.date = payload.date
    transaction.amount = payload.amount
    transaction.label = payload.label
    transaction.payee = payload.payee
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(transaction_id: int, db: Session) -> None:
    transaction = get_transaction(transaction_id, db)
    db.query(TransactionTag).filter(
        TransactionTag.transaction_id == transaction_id
    ).delete()
    db.delete(transaction)
    db.commit()


def add_tag_to_transaction(transaction_id: int, tag_id: int, db: Session) -> Transaction:
    transaction = get_transaction(transaction_id, db)
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=422, detail=f"Tag {tag_id} introuvable")
    existing = db.get(TransactionTag, (transaction_id, tag_id))
    if existing is None:
        db.add(TransactionTag(transaction_id=transaction_id, tag_id=tag_id))
        try:
            db.commit()
        except IntegrityError:
            # Association déjà créée par une requête concurrente : succès idempotent.
            db.rollback()
    return transaction


def remove_tag_from_transaction(transaction_id: int, tag_id: int, db: Session) -> None:
    get_transaction(transaction_id, db)
    association = db.get(TransactionTag, (transaction_id, tag_id))
    if association is not None:
        db.delete(association)
        db.commit()


def count_transactions_for_tag(tag_id: int, db: Session) -> int:
    return db.query(TransactionTag).filter(TransactionTag.tag_id == tag_id).count()
