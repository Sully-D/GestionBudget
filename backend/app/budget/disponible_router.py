from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.budget.service import get_disponible
from app.core.db import get_db

router = APIRouter(prefix="/disponible", tags=["budget"])


@router.get("")
def get_disponible_endpoint(
    account_id: int, period_start: date, db: Session = Depends(get_db)
):
    return {"data": get_disponible(account_id, period_start, db)}
