from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.budget.schema import (
    RevenueOneOffCreate,
    RevenuePeriodSummary,
    RevenueRead,
    RevenueSalaireUpsert,
)
from app.budget.service import (
    add_one_off,
    delete_one_off,
    delete_salaire_correction,
    get_period_summary,
    upsert_salaire,
)
from app.core.db import get_db

router = APIRouter(prefix="/revenues", tags=["budget"])


@router.put("/salaire")
def put_salaire(payload: RevenueSalaireUpsert, db: Session = Depends(get_db)):
    revenue = upsert_salaire(payload, db)
    return {"data": RevenueRead.model_validate(revenue)}


@router.delete("/salaire")
def delete_salaire(account_id: int, period_start: date, db: Session = Depends(get_db)):
    delete_salaire_correction(account_id, period_start, db)
    return {"data": None}


@router.post("/one-off")
def post_one_off(payload: RevenueOneOffCreate, db: Session = Depends(get_db)):
    revenue = add_one_off(payload, db)
    return {"data": RevenueRead.model_validate(revenue)}


@router.delete("/one-off/{revenue_id:int}")
def delete_one_off_endpoint(revenue_id: int, db: Session = Depends(get_db)):
    delete_one_off(revenue_id, db)
    return {"data": None}


@router.get("/period")
def get_period(account_id: int, period_start: date, db: Session = Depends(get_db)):
    summary = get_period_summary(account_id, period_start, db)
    return {"data": summary}
