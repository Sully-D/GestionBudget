from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.budget.model import BudgetTarget, Revenue
from app.budget.schema import (
    BudgetTargetUpsert,
    RevenueOneOffCreate,
    RevenuePeriodSummary,
    RevenueRead,
    RevenueSalaireUpsert,
)
from app.tags.model import Tag


def _get_personal_account_or_404(account_id: int, db: Session) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")
    if account.is_common:
        raise HTTPException(
            status_code=422, detail="Le Compte Commun n'a pas de revenus propres"
        )
    return account


def _get_tag_or_404(tag_id: int, db: Session) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} introuvable")
    return tag


def upsert_salaire(payload: RevenueSalaireUpsert, db: Session) -> Revenue:
    _get_personal_account_or_404(payload.account_id, db)
    existing = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == payload.account_id,
            Revenue.kind == "salaire",
            Revenue.period_start == payload.period_start,
        )
        .first()
    )
    if existing is not None:
        existing.amount = payload.amount
    else:
        existing = Revenue(
            account_id=payload.account_id,
            period_start=payload.period_start,
            kind="salaire",
            amount=payload.amount,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def get_effective_salary_for_period(account_id: int, period_start: date, db: Session) -> Decimal:
    _get_personal_account_or_404(account_id, db)
    correction = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start == period_start,
        )
        .first()
    )
    if correction is not None:
        return correction.amount
    reference = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start.is_(None),
        )
        .first()
    )
    return reference.amount if reference is not None else Decimal("0.00")


def delete_salaire_correction(account_id: int, period_start: date, db: Session) -> None:
    _get_personal_account_or_404(account_id, db)
    correction = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start == period_start,
        )
        .first()
    )
    if correction is None:
        raise HTTPException(
            status_code=404, detail="Aucune correction de salaire pour cette Période"
        )
    db.delete(correction)
    db.commit()


def add_one_off(payload: RevenueOneOffCreate, db: Session) -> Revenue:
    _get_personal_account_or_404(payload.account_id, db)
    revenue = Revenue(
        account_id=payload.account_id,
        period_start=payload.period_start,
        kind="ponctuel",
        amount=payload.amount,
        description=payload.description,
    )
    db.add(revenue)
    db.commit()
    db.refresh(revenue)
    return revenue


def delete_one_off(revenue_id: int, db: Session) -> None:
    revenue = db.get(Revenue, revenue_id)
    if revenue is None or revenue.kind != "ponctuel":
        raise HTTPException(status_code=404, detail=f"Rentrée ponctuelle {revenue_id} introuvable")
    db.delete(revenue)
    db.commit()


def get_period_summary(account_id: int, period_start: date, db: Session) -> RevenuePeriodSummary:
    _get_personal_account_or_404(account_id, db)

    reference = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start.is_(None),
        )
        .first()
    )
    correction = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start == period_start,
        )
        .first()
    )
    one_offs = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "ponctuel",
            Revenue.period_start == period_start,
        )
        .order_by(Revenue.revenue_id)
        .all()
    )

    reference_amount = reference.amount if reference is not None else None
    effective_salary = get_effective_salary_for_period(account_id, period_start, db)
    total = effective_salary + sum((r.amount for r in one_offs), Decimal("0.00"))

    return RevenuePeriodSummary(
        account_id=account_id,
        period_start=period_start,
        reference_amount=reference_amount,
        effective_salary=effective_salary,
        has_correction=correction is not None,
        one_off=[RevenueRead.model_validate(r) for r in one_offs],
        total=total,
    )


def upsert_budget_target(payload: BudgetTargetUpsert, db: Session) -> BudgetTarget:
    _get_personal_account_or_404(payload.account_id, db)
    _get_tag_or_404(payload.tag_id, db)
    existing = (
        db.query(BudgetTarget)
        .filter(
            BudgetTarget.account_id == payload.account_id,
            BudgetTarget.tag_id == payload.tag_id,
        )
        .first()
    )
    if existing is not None:
        existing.percentage = payload.percentage
    else:
        existing = BudgetTarget(
            account_id=payload.account_id,
            tag_id=payload.tag_id,
            percentage=payload.percentage,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def get_budget_targets(account_id: int, db: Session) -> list[BudgetTarget]:
    _get_personal_account_or_404(account_id, db)
    return (
        db.query(BudgetTarget)
        .filter(BudgetTarget.account_id == account_id)
        .order_by(BudgetTarget.target_id)
        .all()
    )


def delete_budget_target(target_id: int, db: Session) -> None:
    target = db.get(BudgetTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Cible {target_id} introuvable")
    db.delete(target)
    db.commit()
