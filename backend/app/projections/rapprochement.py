from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.projections.model import RecurringMatch, RecurringTransaction
from app.projections.service import (
    _advance_recurring_date,
    _anchor_date_for_signature,
    _get_personal_account_or_404,
    _signature_for_transaction,
)
from app.transactions.model import Transaction

DEFAULT_MONTANT_TOLERANCE = Decimal("2.00")
DEFAULT_JOURS_TOLERANCE = 3


def propose_if_match(
    transaction_id: int,
    db: Session,
    montant_tolerance: Decimal = DEFAULT_MONTANT_TOLERANCE,
    jours_tolerance: int = DEFAULT_JOURS_TOLERANCE,
) -> RecurringMatch | None:
    # Best-effort : appelée juste après un commit de Transaction déjà réussi
    # (création manuelle, import OFX/CSV) — une erreur ici ne doit jamais faire
    # échouer la requête HTTP appelante, la Transaction est déjà sauvegardée.
    try:
        return _propose_if_match(transaction_id, db, montant_tolerance, jours_tolerance)
    except Exception:
        db.rollback()
        return None


def _propose_if_match(
    transaction_id: int,
    db: Session,
    montant_tolerance: Decimal,
    jours_tolerance: int,
) -> RecurringMatch | None:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None or transaction.amount >= 0:
        return None

    account = db.get(Account, transaction.account_id)
    if account is None or account.is_common:
        return None

    existing_match = (
        db.query(RecurringMatch)
        .filter(RecurringMatch.transaction_id == transaction_id)
        .first()
    )
    if existing_match is not None:
        return None

    signature = _signature_for_transaction(transaction)

    candidates = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.account_id == account.account_id,
            RecurringTransaction.status == "confirmed",
            RecurringTransaction.signature == signature,
        )
        .order_by(RecurringTransaction.recurring_id)
        .all()
    )

    anchor = _anchor_date_for_signature(
        account.account_id, signature, db, exclude_transaction_id=transaction_id
    )
    if anchor is None:
        return None

    for recurring in candidates:
        expected_date = _advance_recurring_date(anchor, recurring.periodicity)
        if abs((transaction.date - expected_date).days) > jours_tolerance:
            continue
        if abs(transaction.amount - recurring.amount) > montant_tolerance:
            continue

        match = RecurringMatch(
            recurring_id=recurring.recurring_id,
            transaction_id=transaction_id,
            status="pending",
        )
        db.add(match)
        try:
            db.commit()
        except Exception:
            db.rollback()
            continue
        db.refresh(match)
        return match

    return None


def _get_pending_match_or_404(match_id: int, db: Session) -> RecurringMatch:
    match = db.get(RecurringMatch, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Rapprochement {match_id} introuvable")
    if match.status != "pending":
        raise HTTPException(
            status_code=422, detail="Ce Rapprochement n'est plus en attente"
        )
    return match


def confirm_rapprochement(match_id: int, db: Session) -> RecurringMatch:
    match = _get_pending_match_or_404(match_id, db)
    match.status = "confirmed"
    db.commit()
    db.refresh(match)
    return match


def reject_rapprochement(match_id: int, db: Session) -> None:
    match = _get_pending_match_or_404(match_id, db)
    match.status = "rejected"
    db.commit()


def delete_matches_for_transaction(transaction_id: int, db: Session) -> None:
    db.query(RecurringMatch).filter(RecurringMatch.transaction_id == transaction_id).delete()


def list_pending_rapprochements(account_id: int, db: Session) -> list[RecurringMatch]:
    _get_personal_account_or_404(account_id, db)
    return (
        db.query(RecurringMatch)
        .join(RecurringTransaction, RecurringMatch.recurring_id == RecurringTransaction.recurring_id)
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringMatch.status == "pending",
        )
        .order_by(RecurringMatch.match_id)
        .all()
    )
