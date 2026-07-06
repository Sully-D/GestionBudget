from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

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
