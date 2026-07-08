from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.accounts.schema import AccountBalanceRead, AccountRead, AccountUpdate
from app.accounts.service import compute_balance, compute_period
from app.core.db import get_db

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _to_read(account: Account, db: Session) -> AccountRead:
    period_start, period_end = compute_period(account)
    return AccountRead(
        account_id=account.account_id,
        name=account.name,
        is_common=account.is_common,
        start_day=account.start_day,
        reference_balance=account.reference_balance,
        reference_date=account.reference_date,
        balance=compute_balance(account, db),
        period_start=period_start,
        period_end=period_end,
    )


def _get_account_or_404(account_id: int, db: Session) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")
    return account


@router.get("")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(Account).order_by(Account.account_id).all()
    return {"data": [_to_read(account, db) for account in accounts]}


@router.get("/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    account = _get_account_or_404(account_id, db)
    return {"data": _to_read(account, db)}


@router.get("/{account_id}/balance")
def get_account_balance(
    account_id: int,
    as_of: date = Query(...),
    db: Session = Depends(get_db),
):
    account = _get_account_or_404(account_id, db)
    if account.reference_date is not None and as_of < account.reference_date:
        raise HTTPException(
            status_code=422,
            detail="as_of ne peut pas être antérieur à la date de référence du Compte",
        )
    balance = compute_balance(account, db, as_of_date=as_of)
    return {
        "data": AccountBalanceRead(account_id=account_id, as_of=as_of, balance=balance)
    }


@router.put("/{account_id}")
def update_account(
    account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)
):
    account = _get_account_or_404(account_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=422, detail="Mise à jour invalide : contrainte de données violée"
        )
    db.refresh(account)
    return {"data": _to_read(account, db)}
