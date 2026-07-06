from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.core.period import add_months, period_for
from app.projections.model import PlannedExpense, RecurringTransaction
from app.projections.schema import (
    PlannedExpenseSimpleCreate,
    PlannedExpenseSplitCreate,
    PlannedExpenseUpdate,
    ProjectionItemRead,
    RecurringCandidateRead,
    RecurringConfirmCreate,
    RecurringRejectCreate,
    RecurringTransactionUpdate,
)
from app.tags.model import Tag
from app.tags.service import evaluate_transaction_tag
from app.transactions.model import Transaction

RECURRING_PERIODICITY_MONTHS: dict[str, int] = {
    "mensuelle": 1,
    "trimestrielle": 3,
    "annuelle": 12,
}

PERIODICITY_BOUNDS: dict[str, tuple[int, int]] = {
    "hebdomadaire": (6, 8),
    "mensuelle": (27, 32),
    "trimestrielle": (85, 95),
    "annuelle": (355, 375),
}


def _get_personal_account_or_404(account_id: int, db: Session) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")
    if account.is_common:
        raise HTTPException(
            status_code=422, detail="Le Compte Commun n'a pas de Récurrentes"
        )
    return account


def _get_tag_or_404(tag_id: int, db: Session) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} introuvable")
    return tag


def _classify_periodicity(intervals: list[int]) -> str | None:
    categories: set[str] = set()
    for interval in intervals:
        matched: str | None = None
        for name, (low, high) in PERIODICITY_BOUNDS.items():
            if low <= interval <= high:
                matched = name
                break
        if matched is None:
            return None
        categories.add(matched)
    if len(categories) != 1:
        return None
    return categories.pop()


def _signature_for_transaction(transaction: Transaction) -> str:
    return (
        transaction.payee.strip().lower()
        if transaction.payee and transaction.payee.strip()
        else transaction.label.strip().lower()
    )


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2 == 1:
        return ordered[mid]
    return ((ordered[mid - 1] + ordered[mid]) / 2).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def detect_recurring_candidates(
    account_id: int, tolerance_percentage: Decimal, db: Session
) -> list[RecurringCandidateRead]:
    _get_personal_account_or_404(account_id, db)

    transactions = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id, Transaction.amount < 0)
        .order_by(Transaction.date, Transaction.transaction_id)
        .all()
    )

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        signature = _signature_for_transaction(transaction)
        groups[signature].append(transaction)

    existing_signatures = {
        row.signature
        for row in db.query(RecurringTransaction.signature)
        .filter(RecurringTransaction.account_id == account_id)
        .all()
    }

    candidates: list[RecurringCandidateRead] = []
    for signature, group in groups.items():
        if signature in existing_signatures:
            continue
        if len(group) < 3:
            continue

        intervals = [(group[i].date - group[i - 1].date).days for i in range(1, len(group))]
        periodicity = _classify_periodicity(intervals)
        if periodicity is None:
            continue

        reference_amount = _median([t.amount for t in group])
        if any(
            abs(t.amount - reference_amount) / abs(reference_amount) * 100 > tolerance_percentage
            for t in group
        ):
            continue

        latest = group[-1]
        display_label = latest.payee if latest.payee else latest.label

        rule = evaluate_transaction_tag(latest.label, latest.payee, db)
        suggested_tag_id: int | None = None
        suggested_tag_name: str | None = None
        if rule is not None:
            tag = db.get(Tag, rule.tag_id)
            if tag is not None:
                suggested_tag_id = tag.tag_id
                suggested_tag_name = tag.name

        candidates.append(
            RecurringCandidateRead(
                signature=signature,
                label=display_label,
                amount=reference_amount,
                periodicity=periodicity,
                occurrence_count=len(group),
                suggested_tag_id=suggested_tag_id,
                suggested_tag_name=suggested_tag_name,
            )
        )

    return sorted(candidates, key=lambda c: c.signature)


def confirm_recurring(payload: RecurringConfirmCreate, db: Session) -> RecurringTransaction:
    _get_personal_account_or_404(payload.account_id, db)
    if payload.tag_id is not None:
        _get_tag_or_404(payload.tag_id, db)
    recurring = RecurringTransaction(
        account_id=payload.account_id,
        tag_id=payload.tag_id,
        signature=payload.signature,
        label=payload.label,
        amount=payload.amount,
        periodicity=payload.periodicity,
        status="confirmed",
    )
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def reject_recurring_candidate(
    payload: RecurringRejectCreate, db: Session
) -> RecurringTransaction:
    _get_personal_account_or_404(payload.account_id, db)
    recurring = RecurringTransaction(
        account_id=payload.account_id,
        tag_id=None,
        signature=payload.signature,
        label=payload.label,
        amount=payload.amount,
        periodicity=payload.periodicity,
        status="rejected",
    )
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def _get_recurring_or_404(recurring_id: int, db: Session) -> RecurringTransaction:
    recurring = db.get(RecurringTransaction, recurring_id)
    if recurring is None:
        raise HTTPException(status_code=404, detail=f"Récurrente {recurring_id} introuvable")
    return recurring


def update_recurring(
    recurring_id: int, payload: RecurringTransactionUpdate, db: Session
) -> RecurringTransaction:
    recurring = _get_recurring_or_404(recurring_id, db)
    if recurring.status != "confirmed":
        raise HTTPException(
            status_code=422, detail="Seule une Récurrente confirmée peut être éditée"
        )
    if payload.tag_id is not None:
        _get_tag_or_404(payload.tag_id, db)
    recurring.amount = payload.amount
    recurring.periodicity = payload.periodicity
    recurring.tag_id = payload.tag_id
    db.commit()
    db.refresh(recurring)
    return recurring


def delete_recurring(recurring_id: int, db: Session) -> None:
    recurring = _get_recurring_or_404(recurring_id, db)
    db.delete(recurring)
    db.commit()


def list_recurring(
    account_id: int, status: str | None, db: Session
) -> list[RecurringTransaction]:
    _get_personal_account_or_404(account_id, db)
    query = db.query(RecurringTransaction).filter(RecurringTransaction.account_id == account_id)
    if status is not None:
        query = query.filter(RecurringTransaction.status == status)
    return query.order_by(RecurringTransaction.recurring_id).all()


def create_planned_expense(payload: PlannedExpenseSimpleCreate, db: Session) -> PlannedExpense:
    _get_personal_account_or_404(payload.account_id, db)
    _get_tag_or_404(payload.tag_id, db)
    planned_expense = PlannedExpense(
        account_id=payload.account_id,
        tag_id=payload.tag_id,
        series_id=None,
        period_index=None,
        total_periods=None,
        amount=payload.amount,
        date=payload.date,
        description=payload.description,
    )
    db.add(planned_expense)
    db.commit()
    db.refresh(planned_expense)
    return planned_expense


def create_planned_expense_split(
    payload: PlannedExpenseSplitCreate, db: Session
) -> list[PlannedExpense]:
    account = _get_personal_account_or_404(payload.account_id, db)
    _get_tag_or_404(payload.tag_id, db)

    total_periods = payload.total_periods
    period_starts: list[date] = []
    period_start, period_end = period_for(account.start_day, payload.start_date)
    period_starts.append(period_start)
    for _ in range(2, total_periods + 1):
        period_start, period_end = period_for(account.start_day, period_end + timedelta(days=1))
        period_starts.append(period_start)

    base = (payload.total_amount / total_periods).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if base == 0:
        raise HTTPException(
            status_code=422,
            detail="Montant total insuffisant pour ce nombre de périodes",
        )
    amounts: list[Decimal] = [-base for _ in range(total_periods - 1)]
    amounts.append(-payload.total_amount - sum(amounts))

    series_id = str(uuid4())
    planned_expenses: list[PlannedExpense] = []
    for index in range(total_periods):
        planned_expense = PlannedExpense(
            account_id=payload.account_id,
            tag_id=payload.tag_id,
            series_id=series_id,
            period_index=index + 1,
            total_periods=total_periods,
            amount=amounts[index],
            date=period_starts[index],
            description=payload.description,
        )
        db.add(planned_expense)
        planned_expenses.append(planned_expense)
    db.commit()
    for planned_expense in planned_expenses:
        db.refresh(planned_expense)
    return planned_expenses


def _get_planned_expense_or_404(expense_id: int, db: Session) -> PlannedExpense:
    planned_expense = db.get(PlannedExpense, expense_id)
    if planned_expense is None:
        raise HTTPException(
            status_code=404, detail=f"Dépense planifiée {expense_id} introuvable"
        )
    return planned_expense


def update_planned_expense(
    expense_id: int, payload: PlannedExpenseUpdate, db: Session
) -> PlannedExpense:
    planned_expense = _get_planned_expense_or_404(expense_id, db)
    _get_tag_or_404(payload.tag_id, db)
    planned_expense.date = payload.date
    planned_expense.amount = payload.amount
    planned_expense.tag_id = payload.tag_id
    planned_expense.description = payload.description
    db.commit()
    db.refresh(planned_expense)
    return planned_expense


def delete_planned_expense(expense_id: int, db: Session) -> None:
    planned_expense = _get_planned_expense_or_404(expense_id, db)
    if planned_expense.series_id is not None:
        db.query(PlannedExpense).filter(
            PlannedExpense.series_id == planned_expense.series_id
        ).delete()
    else:
        db.delete(planned_expense)
    db.commit()


def list_planned_expenses(account_id: int, db: Session) -> list[PlannedExpense]:
    _get_personal_account_or_404(account_id, db)
    return (
        db.query(PlannedExpense)
        .filter(PlannedExpense.account_id == account_id)
        .order_by(PlannedExpense.date, PlannedExpense.expense_id)
        .all()
    )


def _advance_recurring_date(current: date, periodicity: str) -> date:
    if periodicity == "hebdomadaire":
        return current + timedelta(days=7)
    return add_months(current, RECURRING_PERIODICITY_MONTHS[periodicity])


def _anchor_date_for_signature(account_id: int, signature: str, db: Session) -> date | None:
    transactions = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id, Transaction.amount < 0)
        .all()
    )
    matching_dates = [
        transaction.date
        for transaction in transactions
        if _signature_for_transaction(transaction) == signature
    ]
    if not matching_dates:
        return None
    return max(matching_dates)


def _recurring_occurrences_in_horizon(
    anchor: date, periodicity: str, today: date, horizon_end: date
) -> list[date]:
    current = anchor
    while current <= today:
        current = _advance_recurring_date(current, periodicity)

    occurrences: list[date] = []
    while current <= horizon_end:
        occurrences.append(current)
        current = _advance_recurring_date(current, periodicity)
    return occurrences


def get_projection(
    account_id: int, horizon_months: int, db: Session
) -> list[ProjectionItemRead]:
    _get_personal_account_or_404(account_id, db)
    today = date.today()
    horizon_end = add_months(today, horizon_months)

    tag_names = {tag.tag_id: tag.name for tag in db.query(Tag).all()}

    def resolve_tag(tag_id: int | None) -> tuple[int | None, str | None]:
        if tag_id is not None and tag_id in tag_names:
            return tag_id, tag_names[tag_id]
        return None, None

    entries: list[tuple[ProjectionItemRead, int]] = []

    planned_expenses = (
        db.query(PlannedExpense)
        .filter(
            PlannedExpense.account_id == account_id,
            PlannedExpense.date >= today,
            PlannedExpense.date <= horizon_end,
        )
        .all()
    )
    for planned_expense in planned_expenses:
        tag_id, tag_name = resolve_tag(planned_expense.tag_id)
        entries.append(
            (
                ProjectionItemRead(
                    date=planned_expense.date,
                    type="planifiee",
                    label=planned_expense.description,
                    amount=planned_expense.amount,
                    tag_id=tag_id,
                    tag_name=tag_name,
                ),
                planned_expense.expense_id,
            )
        )

    recurring_transactions = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringTransaction.status == "confirmed",
        )
        .all()
    )
    for recurring in recurring_transactions:
        anchor = _anchor_date_for_signature(account_id, recurring.signature, db)
        if anchor is None:
            continue
        occurrences = _recurring_occurrences_in_horizon(
            anchor, recurring.periodicity, today, horizon_end
        )
        tag_id, tag_name = resolve_tag(recurring.tag_id)
        for occurrence_date in occurrences:
            entries.append(
                (
                    ProjectionItemRead(
                        date=occurrence_date,
                        type="recurrente",
                        label=recurring.label,
                        amount=recurring.amount,
                        tag_id=tag_id,
                        tag_name=tag_name,
                    ),
                    recurring.recurring_id,
                )
            )

    entries.sort(key=lambda entry: (entry[0].date, entry[0].type, entry[0].label, entry[1]))
    return [item for item, _ in entries]
