from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class TransactionCreate(BaseModel):
    account_id: int
    date: date
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    label: str = Field(..., min_length=1)
    payee: str | None = None

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, value: str) -> str:
        # `min_length=1` seul laisse passer une chaîne composée uniquement
        # d'espaces ("   ") : le frontend trim avant envoi, mais un appel API
        # direct pourrait contourner l'obligation du Libellé (AC #6).
        if value.strip() == "":
            raise ValueError("le Libellé ne peut pas être composé uniquement d'espaces")
        return value


class TransactionUpdate(BaseModel):
    # Pas d'`account_id` : le compte n'est pas modifiable via l'édition
    # (AC #1 de la Story 1.4 ne liste que date/montant/Libellé/Tiers).
    date: date
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    label: str = Field(..., min_length=1)
    payee: str | None = None

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("le Libellé ne peut pas être composé uniquement d'espaces")
        return value


class TransactionTagCreate(BaseModel):
    tag_id: int


class TagSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tag_id: int
    name: str


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: int
    account_id: int
    date: date
    amount: Decimal
    label: str
    payee: str | None
    tags: list[TagSummary]

    @field_serializer("amount", when_used="json")
    def _serialize_decimal(self, value: Decimal) -> float:
        # Decimal stays authoritative internally (AD-2/Consistency-Conventions) ;
        # the wire format is a JSON number, matching Story 1.2 Dev Notes.
        return float(value)
