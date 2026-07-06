from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.projections.model import RecurringTransaction
from app.projections.rapprochement import (
    confirm_rapprochement,
    list_pending_rapprochements,
    reject_rapprochement,
)
from app.projections.schema import RapprochementCandidateRead
from app.transactions.model import Transaction

router = APIRouter(prefix="/rapprochement", tags=["projections"])


@router.get("/pending")
def get_pending_rapprochements(account_id: int, db: Session = Depends(get_db)):
    matches = list_pending_rapprochements(account_id, db)
    candidates: list[RapprochementCandidateRead] = []
    for match in matches:
        recurring = db.get(RecurringTransaction, match.recurring_id)
        transaction = db.get(Transaction, match.transaction_id)
        if recurring is None or transaction is None:
            continue
        candidates.append(
            RapprochementCandidateRead(
                match_id=match.match_id,
                recurring_id=match.recurring_id,
                transaction_id=match.transaction_id,
                recurring_label=recurring.label,
                recurring_periodicity=recurring.periodicity,
                transaction_date=transaction.date,
                transaction_amount=transaction.amount,
                transaction_label=transaction.label,
            )
        )
    return {"data": candidates}


@router.post("/{match_id:int}/confirm")
def post_confirm_rapprochement(match_id: int, db: Session = Depends(get_db)):
    match = confirm_rapprochement(match_id, db)
    return {"data": {"match_id": match.match_id, "status": match.status}}


@router.delete("/{match_id:int}")
def delete_rapprochement(match_id: int, db: Session = Depends(get_db)):
    reject_rapprochement(match_id, db)
    return {"data": None}
