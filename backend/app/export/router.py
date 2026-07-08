from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.export.csv_exporter import export_to_csv
from app.export.service import build_full_export

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/full")
def get_full_export(
    format: str = Query(default="json"),
    db: Session = Depends(get_db),
):
    if format not in ("json", "csv"):
        raise HTTPException(status_code=422, detail="format: doit être 'json' ou 'csv'")

    data = build_full_export(db)
    filename_date = date.today().isoformat()

    if format == "csv":
        return Response(
            content="\ufeff" + export_to_csv(data),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="gestion-budget-export-{filename_date}.csv"'
                )
            },
        )

    return Response(
        content=data.model_dump_json(),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="gestion-budget-export-{filename_date}.json"'
            )
        },
    )
