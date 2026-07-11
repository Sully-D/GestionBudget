from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.budget.service import get_repartition_commune
from app.core.db import get_db

router = APIRouter(prefix="/repartition-commune", tags=["budget"])


@router.get("")
def get_repartition_commune_endpoint(
    montant_total: Decimal = Query(..., gt=0, max_digits=12, decimal_places=2),
    tag_id: int = Query(...),
    period_start: date = Query(...),
    db: Session = Depends(get_db),
):
    return {"data": get_repartition_commune(montant_total, tag_id, period_start, db)}
