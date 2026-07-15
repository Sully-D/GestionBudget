from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.projections.schema import (
    RecurringCandidateRead,
    RecurringConfirmCreate,
    RecurringFromTransactionCreate,
    RecurringRejectCreate,
    RecurringTransactionRead,
    RecurringTransactionUpdate,
)
from app.projections.service import (
    confirm_recurring,
    create_recurring_from_transaction,
    delete_recurring,
    detect_recurring_candidates,
    list_recurring,
    reject_recurring_candidate,
    update_recurring,
)

router = APIRouter(prefix="/recurring", tags=["projections"])


@router.get("/candidates")
def get_recurring_candidates(
    account_id: int,
    tolerance_percentage: Decimal = Query(Decimal("10.00"), ge=0, le=100),
    db: Session = Depends(get_db),
):
    candidates = detect_recurring_candidates(account_id, tolerance_percentage, db)
    return {"data": candidates}


@router.post("/confirm")
def post_confirm_recurring(payload: RecurringConfirmCreate, db: Session = Depends(get_db)):
    recurring = confirm_recurring(payload, db)
    return {"data": RecurringTransactionRead.model_validate(recurring)}


@router.post("/from-transaction")
def post_create_recurring_from_transaction(
    payload: RecurringFromTransactionCreate, db: Session = Depends(get_db)
):
    recurring = create_recurring_from_transaction(payload, db)
    return {"data": RecurringTransactionRead.model_validate(recurring)}


@router.post("/reject")
def post_reject_recurring(payload: RecurringRejectCreate, db: Session = Depends(get_db)):
    recurring = reject_recurring_candidate(payload, db)
    return {"data": RecurringTransactionRead.model_validate(recurring)}


@router.get("")
def get_recurring_transactions(
    account_id: int,
    status: Literal["confirmed", "rejected"] | None = None,
    db: Session = Depends(get_db),
):
    recurring_transactions = list_recurring(account_id, status, db)
    return {"data": [RecurringTransactionRead.model_validate(r) for r in recurring_transactions]}


@router.put("/{recurring_id:int}")
def put_recurring(
    recurring_id: int, payload: RecurringTransactionUpdate, db: Session = Depends(get_db)
):
    recurring = update_recurring(recurring_id, payload, db)
    return {"data": RecurringTransactionRead.model_validate(recurring)}


@router.delete("/{recurring_id:int}")
def delete_recurring_endpoint(recurring_id: int, db: Session = Depends(get_db)):
    delete_recurring(recurring_id, db)
    return {"data": None}
