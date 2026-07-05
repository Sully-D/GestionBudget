from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.import_pipeline.csv_parser import ColumnMapping
from app.import_pipeline.pipeline import import_csv, import_ofx, preview_csv
from app.import_pipeline.schema import CsvImportResult, CsvPreviewResult, ImportResult

router = APIRouter(prefix="/import", tags=["import"])


def _require_csv_extension(filename: str | None) -> None:
    if not (filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Le fichier doit avoir l'extension .csv")


@router.post("/ofx")
async def post_import_ofx(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    imported_count, duplicate_count = import_ofx(account_id, raw, db)
    return {
        "data": ImportResult(imported_count=imported_count, duplicate_count=duplicate_count)
    }


@router.post("/csv/preview")
async def post_import_csv_preview(file: UploadFile = File(...)):
    _require_csv_extension(file.filename)
    raw = await file.read()
    preview = preview_csv(raw)
    return {
        "data": CsvPreviewResult(columns=preview.columns, preview_rows=preview.preview_rows)
    }


@router.post("/csv")
async def post_import_csv(
    account_id: int = Form(...),
    date_column: str = Form(...),
    montant_column: str = Form(...),
    libelle_column: str = Form(...),
    tiers_column: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _require_csv_extension(file.filename)
    raw = await file.read()
    mapping = ColumnMapping(
        date_column=date_column,
        montant_column=montant_column,
        libelle_column=libelle_column,
        tiers_column=tiers_column or None,
    )
    imported_count, skipped_count = import_csv(account_id, raw, mapping, db)
    return {
        "data": CsvImportResult(imported_count=imported_count, skipped_count=skipped_count)
    }
