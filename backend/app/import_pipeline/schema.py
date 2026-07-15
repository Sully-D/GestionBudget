from pydantic import BaseModel


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
