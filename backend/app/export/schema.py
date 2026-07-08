from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_serializer


class TransactionExport(BaseModel):
    date: date
    amount: Decimal
    label: str
    payee: str | None
    account: str
    tags: list[str]
    fitid: str | None

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)


class TagExport(BaseModel):
    name: str
    level: int
    parent_name: str | None


class RuleExport(BaseModel):
    condition_type: str
    condition_value: str
    target_tag_name: str
    sort_order: int


class RecurringTransactionExport(BaseModel):
    label: str
    amount: Decimal
    periodicity: str
    tag_name: str | None
    account: str
    status: str

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)


class PlannedExpenseExport(BaseModel):
    date: date
    amount: Decimal
    tag_name: str
    description: str
    account: str
    series_id: str | None
    period_index: int | None
    total_periods: int | None

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)


class BudgetTargetExport(BaseModel):
    account: str
    tag_name: str
    target_percentage: Decimal

    @field_serializer("target_percentage", when_used="json")
    def _serialize_percentage(self, value: Decimal) -> float:
        return float(value)


class RevenueExport(BaseModel):
    account: str
    period_start: date | None
    amount: Decimal
    type: str
    description: str | None

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)


class ExportedData(BaseModel):
    transactions: list[TransactionExport] = []
    tags: list[TagExport] = []
    rules: list[RuleExport] = []
    recurring_transactions: list[RecurringTransactionExport] = []
    planned_expenses: list[PlannedExpenseExport] = []
    budget_targets: list[BudgetTargetExport] = []
    revenues: list[RevenueExport] = []
