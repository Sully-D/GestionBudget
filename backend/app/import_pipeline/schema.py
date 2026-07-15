from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_serializer


class ImportResult(BaseModel):
    imported_count: int
    duplicate_count: int


class SavedCsvMapping(BaseModel):
    date_column: str
    montant_column: str
    libelle_column: str
    tiers_column: str | None


class CsvPreviewResult(BaseModel):
    columns: list[str]
    preview_rows: list[list[str]]
    saved_mapping: SavedCsvMapping | None = None


class CsvImportResult(BaseModel):
    imported_count: int
    skipped_count: int
    duplicate_count: int


class AmbiguousCsvRowOut(BaseModel):
    row_index: int
    date: date
    amount: Decimal
    label: str
    payee: str | None
    existing_label: str
    existing_payee: str | None

    @field_serializer("amount", when_used="json")
    def _serialize_decimal(self, value: Decimal) -> float:
        # Decimal stays authoritative internally ; wire format is a JSON number
        # (même convention que TransactionRead, backend/app/transactions/schema.py).
        return float(value)


class CsvPendingReview(BaseModel):
    pending_review: Literal[True] = True
    ambiguous_rows: list[AmbiguousCsvRowOut]


class CsvRowResolution(BaseModel):
    row_index: int
    decision: Literal["import", "ignore"]
