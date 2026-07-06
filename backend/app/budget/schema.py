from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class RevenueSalaireUpsert(BaseModel):
    account_id: int
    period_start: date | None = None
    amount: Decimal = Field(..., max_digits=12, decimal_places=2, gt=0)


class RevenueOneOffCreate(BaseModel):
    account_id: int
    period_start: date
    amount: Decimal = Field(..., max_digits=12, decimal_places=2, gt=0)
    description: str = Field(..., min_length=1)

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed == "":
            raise ValueError("la description ne peut pas être composée uniquement d'espaces")
        return trimmed


class RevenueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revenue_id: int
    account_id: int
    period_start: date | None
    kind: Literal["salaire", "ponctuel"]
    amount: Decimal
    description: str | None

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> float:
        # Decimal reste autoritaire en interne (AD-2/Consistency-Conventions) ;
        # le format sur le fil est un nombre JSON, cf. AccountRead/TransactionRead.
        return float(value)


class RevenuePeriodSummary(BaseModel):
    account_id: int
    period_start: date
    reference_amount: Decimal | None
    effective_salary: Decimal
    has_correction: bool
    one_off: list[RevenueRead]
    total: Decimal

    @field_serializer("reference_amount", "effective_salary", "total", when_used="json")
    def _serialize_decimal(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class BudgetTargetUpsert(BaseModel):
    account_id: int
    tag_id: int
    percentage: Decimal = Field(..., max_digits=5, decimal_places=2, gt=0, le=100)


class BudgetTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: int
    account_id: int
    tag_id: int
    percentage: Decimal

    @field_serializer("percentage", when_used="json")
    def _serialize_percentage(self, value: Decimal) -> float:
        return float(value)


class TagTrackingRead(BaseModel):
    tag_id: int
    tag_name: str
    parent_id: int | None
    level: int
    spent: Decimal
    target_percentage: Decimal | None
    target_amount: Decimal | None
    gap: Decimal | None
    projection: Decimal | None

    @field_serializer("spent", when_used="json")
    def _serialize_spent(self, value: Decimal) -> float:
        return float(value)

    @field_serializer(
        "target_percentage", "target_amount", "gap", "projection", when_used="json"
    )
    def _serialize_nullable_decimal(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class DisponibleRead(BaseModel):
    account_id: int
    period_start: date
    period_end: date
    revenus: Decimal
    charges_recurrentes: Decimal
    depenses_planifiees: Decimal
    depenses_courantes: Decimal
    disponible: Decimal

    @field_serializer(
        "revenus",
        "charges_recurrentes",
        "depenses_planifiees",
        "depenses_courantes",
        "disponible",
        when_used="json",
    )
    def _serialize_decimal(self, value: Decimal) -> float:
        return float(value)
