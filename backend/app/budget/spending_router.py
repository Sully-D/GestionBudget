from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.budget.service import get_tag_spending
from app.core.db import get_db

router = APIRouter(prefix="/tag-spending", tags=["budget"])


@router.get("")
def get_tag_spending_endpoint(
    account_id: int, period_start: date, db: Session = Depends(get_db)
):
    return {"data": get_tag_spending(account_id, period_start, db)}
