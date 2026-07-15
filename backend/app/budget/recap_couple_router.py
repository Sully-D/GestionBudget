from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.budget.schema import CoupleChargesPercentageUpdate
from app.budget.service import get_recap_couple, update_couple_charges_percentage
from app.core.db import get_db

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/recap-couple")
def get_recap_couple_endpoint(
    account_id: int = Query(...),
    months: int = Query(..., ge=1, le=120),
    db: Session = Depends(get_db),
):
    return {"data": get_recap_couple(account_id, months, db)}


@router.patch("/couple-charges-percentage")
def patch_couple_charges_percentage(
    payload: CoupleChargesPercentageUpdate, db: Session = Depends(get_db)
):
    account = update_couple_charges_percentage(payload, db)
    return {
        "data": {
            "account_id": account.account_id,
            "couple_charges_percentage": account.couple_charges_percentage,
        }
    }
