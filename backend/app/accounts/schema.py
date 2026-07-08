from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: int
    name: str
    is_common: bool
    start_day: int
    reference_balance: Decimal | None
    reference_date: date | None
    balance: Decimal
    period_start: date
    period_end: date

    @field_serializer("reference_balance", "balance", when_used="json")
    def _serialize_decimal(self, value: Decimal | None) -> float | None:
        # Decimal stays authoritative internally (AD-2/Consistency-Conventions) ;
        # the wire format is a JSON number, matching Story 1.2 Dev Notes.
        return float(value) if value is not None else None


class AccountBalanceRead(BaseModel):
    account_id: int
    as_of: date
    balance: Decimal

    @field_serializer("balance", when_used="json")
    def _serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class AccountUpdate(BaseModel):
    start_day: int | None = Field(default=None, ge=1, le=28)
    reference_balance: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    reference_date: date | None = None

    @model_validator(mode="after")
    def _validate_provided_fields(self) -> "AccountUpdate":
        fields_set = self.model_fields_set

        if "start_day" in fields_set and self.start_day is None:
            raise ValueError("start_day ne peut pas être null")

        has_balance = "reference_balance" in fields_set
        has_date = "reference_date" in fields_set
        if has_balance != has_date:
            raise ValueError(
                "reference_balance et reference_date doivent être fournis ensemble ou absents ensemble"
            )
        if has_balance and has_date and (self.reference_balance is None) != (self.reference_date is None):
            raise ValueError(
                "reference_balance et reference_date doivent être tous deux null ou tous deux renseignés"
            )
        return self
