from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

Periodicity = Literal["hebdomadaire", "mensuelle", "trimestrielle", "annuelle"]


class RecurringCandidateRead(BaseModel):
    signature: str
    label: str
    amount: Decimal
    periodicity: str
    occurrence_count: int
    suggested_tag_id: int | None
    suggested_tag_name: str | None

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)


class RecurringConfirmCreate(BaseModel):
    account_id: int
    signature: str
    label: str
    amount: Decimal = Field(..., max_digits=12, decimal_places=2, lt=0)
    periodicity: Periodicity
    tag_id: int | None = None


class RecurringRejectCreate(BaseModel):
    account_id: int
    signature: str
    label: str
    amount: Decimal = Field(..., max_digits=12, decimal_places=2, lt=0)
    periodicity: Periodicity


class RecurringTransactionUpdate(BaseModel):
    amount: Decimal = Field(..., max_digits=12, decimal_places=2, lt=0)
    periodicity: Periodicity
    tag_id: int | None = None


class RecurringTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recurring_id: int
    account_id: int
    tag_id: int | None
    label: str
    amount: Decimal
    periodicity: str
    status: str

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)


class PlannedExpenseSimpleCreate(BaseModel):
    account_id: int
    tag_id: int
    date: date
    amount: Decimal = Field(..., max_digits=12, decimal_places=2, lt=0)
    description: str

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed == "":
            raise ValueError("la description ne peut pas être composée uniquement d'espaces")
        return trimmed


class PlannedExpenseSplitCreate(BaseModel):
    account_id: int
    tag_id: int
    start_date: date
    total_amount: Decimal = Field(..., max_digits=12, decimal_places=2, gt=0)
    total_periods: int = Field(..., ge=2, le=60)
    description: str

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed == "":
            raise ValueError("la description ne peut pas être composée uniquement d'espaces")
        return trimmed


class PlannedExpenseUpdate(BaseModel):
    date: date
    amount: Decimal = Field(..., max_digits=12, decimal_places=2, lt=0)
    tag_id: int
    description: str

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed == "":
            raise ValueError("la description ne peut pas être composée uniquement d'espaces")
        return trimmed


class PlannedExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expense_id: int
    account_id: int
    tag_id: int
    series_id: str | None
    period_index: int | None
    total_periods: int | None
    amount: Decimal
    date: date
    description: str

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)


class ProjectionItemRead(BaseModel):
    date: date
    type: Literal["recurrente", "planifiee"]
    label: str
    amount: Decimal
    tag_id: int | None
    tag_name: str | None

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)
