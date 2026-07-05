from pydantic import BaseModel


class ImportResult(BaseModel):
    imported_count: int
    duplicate_count: int


class CsvPreviewResult(BaseModel):
    columns: list[str]
    preview_rows: list[list[str]]


class CsvImportResult(BaseModel):
    imported_count: int
    skipped_count: int
