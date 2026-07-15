from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.import_pipeline.csv_parser import ColumnMapping
from app.import_pipeline.dedup import RowDecision
from app.import_pipeline.pipeline import CsvImportPending, import_csv, import_ofx, preview_csv
from app.import_pipeline.schema import (
    AmbiguousCsvRowOut,
    CsvImportResult,
    CsvPendingReview,
    CsvPreviewResult,
    CsvRowResolution,
    ImportResult,
    SavedCsvMapping,
)
from app.projections.rapprochement import propose_if_match

_RESOLUTIONS_ADAPTER = TypeAdapter(list[CsvRowResolution])


def _parse_resolutions(raw: str | None) -> dict[int, RowDecision] | None:
    if raw is None:
        return None
    try:
        items = _RESOLUTIONS_ADAPTER.validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="Paramètre resolutions invalide.") from exc
    if len(items) != len({item.row_index for item in items}):
        raise HTTPException(
            status_code=400, detail="Paramètre resolutions invalide : row_index en double."
        )
    return {item.row_index: item.decision for item in items}

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
    imported_count, duplicate_count, transaction_ids = import_ofx(account_id, raw, db)
    for transaction_id in transaction_ids:
        propose_if_match(transaction_id, db)
    return {
        "data": ImportResult(imported_count=imported_count, duplicate_count=duplicate_count)
    }


@router.post("/csv/preview")
async def post_import_csv_preview(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _require_csv_extension(file.filename)
    raw = await file.read()
    preview, saved_mapping = preview_csv(raw, account_id, db)
    return {
        "data": CsvPreviewResult(
            columns=preview.columns,
            preview_rows=preview.preview_rows,
            saved_mapping=(
                SavedCsvMapping(
                    date_column=saved_mapping.date_column,
                    montant_column=saved_mapping.montant_column,
                    libelle_column=saved_mapping.libelle_column,
                    tiers_column=saved_mapping.tiers_column,
                )
                if saved_mapping is not None
                else None
            ),
        )
    }


@router.post("/csv")
async def post_import_csv(
    account_id: int = Form(...),
    date_column: str = Form(...),
    montant_column: str = Form(...),
    libelle_column: str = Form(...),
    tiers_column: str | None = Form(None),
    resolutions: str | None = Form(None),
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
    parsed_resolutions = _parse_resolutions(resolutions)
    outcome = import_csv(account_id, raw, mapping, db, parsed_resolutions)

    if isinstance(outcome, CsvImportPending):
        return {
            "data": CsvPendingReview(
                ambiguous_rows=[
                    AmbiguousCsvRowOut(
                        row_index=row.row_index,
                        date=row.date,
                        amount=row.amount,
                        label=row.label,
                        payee=row.payee,
                        existing_label=row.existing_label,
                        existing_payee=row.existing_payee,
                    )
                    for row in outcome.ambiguous_rows
                ]
            )
        }

    for transaction_id in outcome.transaction_ids:
        propose_if_match(transaction_id, db)
    return {
        "data": CsvImportResult(
            imported_count=outcome.imported_count,
            skipped_count=outcome.skipped_count,
            duplicate_count=outcome.duplicate_count,
        )
    }
