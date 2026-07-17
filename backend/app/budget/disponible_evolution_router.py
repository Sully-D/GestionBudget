from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.budget.service import get_disponible_evolution
from app.core.db import get_db

router = APIRouter(prefix="/disponible-evolution", tags=["budget"])


@router.get("")
def get_disponible_evolution_endpoint(account_id: int, db: Session = Depends(get_db)):
    return {"data": get_disponible_evolution(account_id, db)}
