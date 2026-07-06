from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.accounts.service import compute_period
from app.budget.model import BudgetTarget, Revenue
from app.budget.schema import (
    BudgetTargetUpsert,
    DisponibleRead,
    RevenueOneOffCreate,
    RevenuePeriodSummary,
    RevenueRead,
    RevenueSalaireUpsert,
    TagTrackingRead,
)
from app.core.period import add_months, period_for
from app.projections.model import PlannedExpense, RecurringMatch, RecurringTransaction
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag

RECURRING_PERIODICITY_MONTHS: dict[str, int] = {
    "mensuelle": 1,
    "trimestrielle": 3,
    "annuelle": 12,
}


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


def get_tag_tracking(account_id: int, period_start: date, db: Session) -> list[TagTrackingRead]:
    account = _get_personal_account_or_404(account_id, db)
    today = date.today()
    period_start, period_end = period_for(account.start_day, period_start)
    is_current_period = period_start == compute_period(account, today)[0]

    rows = (
        db.query(TransactionTag.transaction_id, TransactionTag.tag_id, Transaction.amount)
        .join(Transaction, Transaction.transaction_id == TransactionTag.transaction_id)
        .filter(
            Transaction.account_id == account_id,
            Transaction.date >= period_start,
            Transaction.date <= period_end,
            Transaction.amount < 0,
        )
        .all()
    )
    txn_tag_ids: dict[int, set[int]] = {}
    txn_amount: dict[int, Decimal] = {}
    for transaction_id, tag_id, amount in rows:
        txn_tag_ids.setdefault(transaction_id, set()).add(tag_id)
        txn_amount[transaction_id] = abs(amount)

    tags = db.query(Tag).all()
    tag_by_id = {tag.tag_id: tag for tag in tags}

    # Auto-tagué ou remonté par un enfant, une même transaction ne doit compter
    # qu'une fois par ancêtre (évite le double comptage si elle porte à la fois
    # un tag et l'un de ses ancêtres/descendants).
    ancestors_or_self: dict[int, list[int]] = {}
    for tag in tags:
        chain = []
        current: Tag | None = tag
        while current is not None:
            chain.append(current.tag_id)
            current = tag_by_id.get(current.parent_id) if current.parent_id is not None else None
        ancestors_or_self[tag.tag_id] = chain

    total_spent: dict[int, Decimal] = {tag.tag_id: Decimal("0.00") for tag in tags}
    for transaction_id, tag_ids in txn_tag_ids.items():
        amount = txn_amount[transaction_id]
        affected_tag_ids: set[int] = set()
        for tag_id in tag_ids:
            affected_tag_ids.update(ancestors_or_self.get(tag_id, ()))
        for tag_id in affected_tag_ids:
            if tag_id in total_spent:
                total_spent[tag_id] += amount

    targets = db.query(BudgetTarget).filter(BudgetTarget.account_id == account_id).all()
    target_by_tag = {
        target.tag_id: target for target in targets if target.tag_id in tag_by_id
    }

    total_revenue = get_period_summary(account_id, period_start, db).total
    jours_totaux = (period_end - period_start).days + 1
    jours_ecoules = (today - period_start).days + 1

    included_tag_ids = {
        tag_id for tag_id, spent in total_spent.items() if spent != 0
    } | set(target_by_tag.keys())

    result: list[TagTrackingRead] = []
    for tag_id in sorted(included_tag_ids):
        tag = tag_by_id[tag_id]
        spent = total_spent.get(tag_id, Decimal("0.00"))
        target = target_by_tag.get(tag_id)

        target_percentage: Decimal | None = None
        target_amount: Decimal | None = None
        gap: Decimal | None = None
        projection: Decimal | None = None

        if target is not None:
            target_percentage = target.percentage
            target_amount = (target.percentage / Decimal(100) * total_revenue).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            gap = target_amount - spent
            projection = (
                ((spent / jours_ecoules) * jours_totaux).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if is_current_period
                else None
            )

        result.append(
            TagTrackingRead(
                tag_id=tag.tag_id,
                tag_name=tag.name,
                parent_id=tag.parent_id,
                level=tag.level,
                spent=spent,
                target_percentage=target_percentage,
                target_amount=target_amount,
                gap=gap,
                projection=projection,
            )
        )

    return result


def _signature_for_transaction(transaction: Transaction) -> str:
    return (
        transaction.payee.strip().lower()
        if transaction.payee and transaction.payee.strip()
        else transaction.label.strip().lower()
    )


def _advance_recurring_date(current: date, periodicity: str) -> date:
    if periodicity == "hebdomadaire":
        return current + timedelta(days=7)
    return add_months(current, RECURRING_PERIODICITY_MONTHS[periodicity])


def _recurring_anchor_date(account_id: int, signature: str, db: Session) -> date | None:
    transactions = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id, Transaction.amount < 0)
        .all()
    )
    pending_transaction_ids = {
        row.transaction_id
        for row in db.query(RecurringMatch.transaction_id)
        .filter(RecurringMatch.status == "pending")
        .all()
    }
    matching_dates = [
        transaction.date
        for transaction in transactions
        if _signature_for_transaction(transaction) == signature
        and transaction.transaction_id not in pending_transaction_ids
    ]
    if not matching_dates:
        return None
    return max(matching_dates)


def _is_recurring_due_in_period(
    anchor: date, periodicity: str, period_start: date, period_end: date
) -> bool:
    current = _advance_recurring_date(anchor, periodicity)
    while current < period_start:
        current = _advance_recurring_date(current, periodicity)
    return current <= period_end


def _charges_recurrentes_for_period(
    account_id: int, period_start: date, period_end: date, db: Session
) -> Decimal:
    confirmed_recurring = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringTransaction.status == "confirmed",
        )
        .all()
    )
    if not confirmed_recurring:
        return Decimal("0.00")

    total = Decimal("0.00")
    realized_ids: set[int] = set()
    realized_rows = (
        db.query(RecurringMatch.recurring_id, Transaction.amount)
        .join(Transaction, Transaction.transaction_id == RecurringMatch.transaction_id)
        .join(
            RecurringTransaction,
            RecurringTransaction.recurring_id == RecurringMatch.recurring_id,
        )
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringTransaction.status == "confirmed",
            RecurringMatch.status == "confirmed",
            Transaction.date >= period_start,
            Transaction.date <= period_end,
        )
        .all()
    )
    for recurring_id, amount in realized_rows:
        total += abs(amount)
        realized_ids.add(recurring_id)

    # Une Récurrente déjà liée à une Transaction de la Période (même via un
    # Rapprochement `pending`, pas encore confirmé) ne doit pas recevoir de
    # charge projetée en plus : la Transaction reste comptée dans les Dépenses
    # courantes tant que non confirmée, ajouter la charge projetée compterait
    # la même dépense deux fois.
    matched_ids_in_period = {
        row.recurring_id
        for row in db.query(RecurringMatch.recurring_id)
        .join(Transaction, Transaction.transaction_id == RecurringMatch.transaction_id)
        .join(
            RecurringTransaction,
            RecurringTransaction.recurring_id == RecurringMatch.recurring_id,
        )
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringTransaction.status == "confirmed",
            RecurringMatch.status.in_(["pending", "confirmed"]),
            Transaction.date >= period_start,
            Transaction.date <= period_end,
        )
        .all()
    }

    for recurring in confirmed_recurring:
        if recurring.recurring_id in matched_ids_in_period:
            continue
        anchor = _recurring_anchor_date(account_id, recurring.signature, db)
        if anchor is None:
            continue
        if _is_recurring_due_in_period(anchor, recurring.periodicity, period_start, period_end):
            total += abs(recurring.amount)

    return total


def _depenses_courantes_for_period(
    account_id: int, period_start: date, period_end: date, db: Session
) -> Decimal:
    matched_transaction_ids = {
        row.transaction_id
        for row in db.query(RecurringMatch.transaction_id)
        .join(
            RecurringTransaction,
            RecurringTransaction.recurring_id == RecurringMatch.recurring_id,
        )
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringMatch.status == "confirmed",
        )
        .all()
    }

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.date >= period_start,
            Transaction.date <= period_end,
            Transaction.amount < 0,
        )
        .all()
    )
    return sum(
        (abs(t.amount) for t in transactions if t.transaction_id not in matched_transaction_ids),
        Decimal("0.00"),
    )


def _depenses_planifiees_for_period(
    account_id: int, period_start: date, period_end: date, db: Session
) -> Decimal:
    total = (
        db.query(func.sum(PlannedExpense.amount))
        .filter(
            PlannedExpense.account_id == account_id,
            PlannedExpense.date >= period_start,
            PlannedExpense.date <= period_end,
        )
        .scalar()
        or Decimal("0.00")
    )
    return abs(total)


def get_disponible(account_id: int, period_start: date, db: Session) -> DisponibleRead:
    account = _get_personal_account_or_404(account_id, db)
    period_start, period_end = period_for(account.start_day, period_start)

    revenus = get_period_summary(account_id, period_start, db).total
    charges_recurrentes = _charges_recurrentes_for_period(account_id, period_start, period_end, db)
    depenses_planifiees = _depenses_planifiees_for_period(account_id, period_start, period_end, db)
    depenses_courantes = _depenses_courantes_for_period(account_id, period_start, period_end, db)
    disponible = revenus - charges_recurrentes - depenses_planifiees - depenses_courantes

    return DisponibleRead(
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        revenus=revenus,
        charges_recurrentes=charges_recurrentes,
        depenses_planifiees=depenses_planifiees,
        depenses_courantes=depenses_courantes,
        disponible=disponible,
    )
