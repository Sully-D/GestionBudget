from sqlalchemy.orm import Session, selectinload

from app.accounts.model import Account
from app.budget.model import BudgetTarget, Revenue
from app.export.schema import (
    BudgetTargetExport,
    ExportedData,
    PlannedExpenseExport,
    RecurringTransactionExport,
    RevenueExport,
    RuleExport,
    TagExport,
    TransactionExport,
)
from app.projections.model import PlannedExpense, RecurringTransaction
from app.tags.model import Rule, Tag
from app.transactions.model import Transaction


def _tag_path(tag_id: int | None, tags_by_id: dict[int, Tag]) -> str | None:
    if tag_id is None:
        return None
    tag = tags_by_id.get(tag_id)
    if tag is None:
        return None

    names: list[str] = []
    current: Tag | None = tag
    while current is not None:
        names.append(current.name)
        current = tags_by_id.get(current.parent_id) if current.parent_id is not None else None
    return " > ".join(reversed(names))


def build_full_export(db: Session) -> ExportedData:
    accounts_by_id = {a.account_id: a.name for a in db.query(Account).all()}
    tags = db.query(Tag).order_by(Tag.tag_id).all()
    tags_by_id = {tag.tag_id: tag for tag in tags}

    transactions = (
        db.query(Transaction)
        .options(selectinload(Transaction.tags))
        .order_by(Transaction.date, Transaction.transaction_id)
        .all()
    )
    rules = db.query(Rule).order_by(Rule.sort_order).all()
    recurring_transactions = (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.status == "confirmed")
        .order_by(RecurringTransaction.recurring_id)
        .all()
    )
    planned_expenses = db.query(PlannedExpense).order_by(PlannedExpense.date).all()
    budget_targets = db.query(BudgetTarget).order_by(BudgetTarget.target_id).all()
    revenues = db.query(Revenue).order_by(Revenue.period_start).all()

    return ExportedData(
        transactions=[
            TransactionExport(
                date=t.date,
                amount=t.amount,
                label=t.label,
                payee=t.payee,
                account=accounts_by_id.get(t.account_id, ""),
                tags=[
                    path
                    for tag in t.tags
                    if (path := _tag_path(tag.tag_id, tags_by_id)) is not None
                ],
                fitid=t.fitid,
            )
            for t in transactions
        ],
        tags=[
            TagExport(
                name=tag.name,
                level=tag.level,
                parent_name=getattr(tags_by_id.get(tag.parent_id), "name", None),
            )
            for tag in tags
        ],
        rules=[
            RuleExport(
                condition_type=rule.condition_type,
                condition_value=rule.condition_value,
                target_tag_name=_tag_path(rule.tag_id, tags_by_id) or "",
                sort_order=rule.sort_order,
            )
            for rule in rules
        ],
        recurring_transactions=[
            RecurringTransactionExport(
                label=r.label,
                amount=r.amount,
                periodicity=r.periodicity,
                tag_name=_tag_path(r.tag_id, tags_by_id),
                account=accounts_by_id.get(r.account_id, ""),
                status=r.status,
            )
            for r in recurring_transactions
        ],
        planned_expenses=[
            PlannedExpenseExport(
                date=p.date,
                amount=p.amount,
                tag_name=_tag_path(p.tag_id, tags_by_id) or "",
                description=p.description,
                account=accounts_by_id.get(p.account_id, ""),
                series_id=p.series_id,
                period_index=p.period_index,
                total_periods=p.total_periods,
            )
            for p in planned_expenses
        ],
        budget_targets=[
            BudgetTargetExport(
                account=accounts_by_id.get(t.account_id, ""),
                tag_name=_tag_path(t.tag_id, tags_by_id) or "",
                target_percentage=t.percentage,
            )
            for t in budget_targets
        ],
        revenues=[
            RevenueExport(
                account=accounts_by_id.get(r.account_id, ""),
                period_start=r.period_start,
                amount=r.amount,
                type=r.kind,
                description=r.description,
            )
            for r in revenues
        ],
    )
