from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.budget.schema import BudgetTargetRead, BudgetTargetUpsert
from app.budget.service import delete_budget_target, get_budget_targets, upsert_budget_target
from app.core.db import get_db

router = APIRouter(prefix="/budget-targets", tags=["budget"])


@router.get("")
def get_budget_targets_endpoint(account_id: int, db: Session = Depends(get_db)):
    targets = get_budget_targets(account_id, db)
    return {"data": [BudgetTargetRead.model_validate(t) for t in targets]}


@router.put("")
def put_budget_target(payload: BudgetTargetUpsert, db: Session = Depends(get_db)):
    target = upsert_budget_target(payload, db)
    return {"data": BudgetTargetRead.model_validate(target)}


@router.delete("/{target_id:int}")
def delete_budget_target_endpoint(target_id: int, db: Session = Depends(get_db)):
    delete_budget_target(target_id, db)
    return {"data": None}
