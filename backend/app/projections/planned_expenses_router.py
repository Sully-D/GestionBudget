from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.projections.schema import (
    PlannedExpenseRead,
    PlannedExpenseSimpleCreate,
    PlannedExpenseSplitCreate,
    PlannedExpenseUpdate,
)
from app.projections.service import (
    create_planned_expense,
    create_planned_expense_split,
    delete_planned_expense,
    list_planned_expenses,
    update_planned_expense,
)

router = APIRouter(prefix="/planned-expenses", tags=["projections"])


@router.post("")
def post_planned_expense(payload: PlannedExpenseSimpleCreate, db: Session = Depends(get_db)):
    planned_expense = create_planned_expense(payload, db)
    return {"data": PlannedExpenseRead.model_validate(planned_expense)}


@router.post("/split")
def post_planned_expense_split(
    payload: PlannedExpenseSplitCreate, db: Session = Depends(get_db)
):
    planned_expenses = create_planned_expense_split(payload, db)
    return {"data": [PlannedExpenseRead.model_validate(p) for p in planned_expenses]}


@router.get("")
def get_planned_expenses(account_id: int, db: Session = Depends(get_db)):
    planned_expenses = list_planned_expenses(account_id, db)
    return {"data": [PlannedExpenseRead.model_validate(p) for p in planned_expenses]}


@router.put("/{expense_id:int}")
def put_planned_expense(
    expense_id: int, payload: PlannedExpenseUpdate, db: Session = Depends(get_db)
):
    planned_expense = update_planned_expense(expense_id, payload, db)
    return {"data": PlannedExpenseRead.model_validate(planned_expense)}


@router.delete("/{expense_id:int}")
def delete_planned_expense_endpoint(expense_id: int, db: Session = Depends(get_db)):
    delete_planned_expense(expense_id, db)
    return {"data": None}
