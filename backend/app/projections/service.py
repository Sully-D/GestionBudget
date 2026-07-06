from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.projections.model import RecurringTransaction
from app.projections.schema import (
    RecurringCandidateRead,
    RecurringConfirmCreate,
    RecurringRejectCreate,
    RecurringTransactionUpdate,
)
from app.tags.model import Tag
from app.tags.service import evaluate_transaction_tag
from app.transactions.model import Transaction

PERIODICITY_BOUNDS: dict[str, tuple[int, int]] = {
    "hebdomadaire": (6, 8),
    "mensuelle": (27, 32),
    "trimestrielle": (85, 95),
    "annuelle": (355, 375),
}


def _get_personal_account_or_404(account_id: int, db: Session) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")
    if account.is_common:
        raise HTTPException(
            status_code=422, detail="Le Compte Commun n'a pas de Récurrentes"
        )
    return account


def _get_tag_or_404(tag_id: int, db: Session) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} introuvable")
    return tag


def _classify_periodicity(intervals: list[int]) -> str | None:
    categories: set[str] = set()
    for interval in intervals:
        matched: str | None = None
        for name, (low, high) in PERIODICITY_BOUNDS.items():
            if low <= interval <= high:
                matched = name
                break
        if matched is None:
            return None
        categories.add(matched)
    if len(categories) != 1:
        return None
    return categories.pop()


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2 == 1:
        return ordered[mid]
    return ((ordered[mid - 1] + ordered[mid]) / 2).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def detect_recurring_candidates(
    account_id: int, tolerance_percentage: Decimal, db: Session
) -> list[RecurringCandidateRead]:
    _get_personal_account_or_404(account_id, db)

    transactions = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id, Transaction.amount < 0)
        .order_by(Transaction.date, Transaction.transaction_id)
        .all()
    )

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        signature = (
            transaction.payee.strip().lower()
            if transaction.payee and transaction.payee.strip()
            else transaction.label.strip().lower()
        )
        groups[signature].append(transaction)

    existing_signatures = {
        row.signature
        for row in db.query(RecurringTransaction.signature)
        .filter(RecurringTransaction.account_id == account_id)
        .all()
    }

    candidates: list[RecurringCandidateRead] = []
    for signature, group in groups.items():
        if signature in existing_signatures:
            continue
        if len(group) < 3:
            continue

        intervals = [(group[i].date - group[i - 1].date).days for i in range(1, len(group))]
        periodicity = _classify_periodicity(intervals)
        if periodicity is None:
            continue

        reference_amount = _median([t.amount for t in group])
        if any(
            abs(t.amount - reference_amount) / abs(reference_amount) * 100 > tolerance_percentage
            for t in group
        ):
            continue

        latest = group[-1]
        display_label = latest.payee if latest.payee else latest.label

        rule = evaluate_transaction_tag(latest.label, latest.payee, db)
        suggested_tag_id: int | None = None
        suggested_tag_name: str | None = None
        if rule is not None:
            tag = db.get(Tag, rule.tag_id)
            if tag is not None:
                suggested_tag_id = tag.tag_id
                suggested_tag_name = tag.name

        candidates.append(
            RecurringCandidateRead(
                signature=signature,
                label=display_label,
                amount=reference_amount,
                periodicity=periodicity,
                occurrence_count=len(group),
                suggested_tag_id=suggested_tag_id,
                suggested_tag_name=suggested_tag_name,
            )
        )

    return sorted(candidates, key=lambda c: c.signature)


def confirm_recurring(payload: RecurringConfirmCreate, db: Session) -> RecurringTransaction:
    _get_personal_account_or_404(payload.account_id, db)
    if payload.tag_id is not None:
        _get_tag_or_404(payload.tag_id, db)
    recurring = RecurringTransaction(
        account_id=payload.account_id,
        tag_id=payload.tag_id,
        signature=payload.signature,
        label=payload.label,
        amount=payload.amount,
        periodicity=payload.periodicity,
        status="confirmed",
    )
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def reject_recurring_candidate(
    payload: RecurringRejectCreate, db: Session
) -> RecurringTransaction:
    _get_personal_account_or_404(payload.account_id, db)
    recurring = RecurringTransaction(
        account_id=payload.account_id,
        tag_id=None,
        signature=payload.signature,
        label=payload.label,
        amount=payload.amount,
        periodicity=payload.periodicity,
        status="rejected",
    )
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def _get_recurring_or_404(recurring_id: int, db: Session) -> RecurringTransaction:
    recurring = db.get(RecurringTransaction, recurring_id)
    if recurring is None:
        raise HTTPException(status_code=404, detail=f"Récurrente {recurring_id} introuvable")
    return recurring


def update_recurring(
    recurring_id: int, payload: RecurringTransactionUpdate, db: Session
) -> RecurringTransaction:
    recurring = _get_recurring_or_404(recurring_id, db)
    if recurring.status != "confirmed":
        raise HTTPException(
            status_code=422, detail="Seule une Récurrente confirmée peut être éditée"
        )
    if payload.tag_id is not None:
        _get_tag_or_404(payload.tag_id, db)
    recurring.amount = payload.amount
    recurring.periodicity = payload.periodicity
    recurring.tag_id = payload.tag_id
    db.commit()
    db.refresh(recurring)
    return recurring


def delete_recurring(recurring_id: int, db: Session) -> None:
    recurring = _get_recurring_or_404(recurring_id, db)
    db.delete(recurring)
    db.commit()


def list_recurring(
    account_id: int, status: str | None, db: Session
) -> list[RecurringTransaction]:
    _get_personal_account_or_404(account_id, db)
    query = db.query(RecurringTransaction).filter(RecurringTransaction.account_id == account_id)
    if status is not None:
        query = query.filter(RecurringTransaction.status == status)
    return query.order_by(RecurringTransaction.recurring_id).all()
