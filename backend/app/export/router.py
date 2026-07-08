from datetime import date
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.export.csv_exporter import export_to_csv
from app.export.service import build_filtered_export, build_full_export

router = APIRouter(prefix="/export", tags=["export"])


def _content_disposition(filename_base: str, ext: str) -> str:
    safe_base = "".join(c if (c.isascii() and c.isalnum()) or c in "._- " else "_" for c in filename_base)
    return (
        f'attachment; filename="{safe_base}.{ext}"; '
        f"filename*=UTF-8''{quote(filename_base)}.{ext}"
    )


@router.get("/full")
def get_full_export(
    format: Literal["json", "csv"] = Query(default="json"),
    db: Session = Depends(get_db),
):
    data = build_full_export(db)
    filename_base = f"gestion-budget-export-{date.today().isoformat()}"

    if format == "csv":
        return Response(
            content="\ufeff" + export_to_csv(data),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(filename_base, "csv")},
        )

    return Response(
        content=data.model_dump_json(),
        media_type="application/json",
        headers={"Content-Disposition": _content_disposition(filename_base, "json")},
    )


@router.get("/filtered")
def get_filtered_export(
    account_id: int = Query(...),
    format: Literal["json", "csv"] = Query(default="json"),
    period_start: date | None = Query(default=None),
    period_end: date | None = Query(default=None),
    reference_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    data, account_name, resolved_start, resolved_end = build_filtered_export(
        account_id, period_start, period_end, reference_date, db
    )
    filename_base = f"gestion-budget-export-{account_name}-{resolved_start}-{resolved_end}"

    if format == "csv":
        return Response(
            content="\ufeff" + export_to_csv(data, omit_empty_sections=True),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(filename_base, "csv")},
        )

    return Response(
        content=data.model_dump_json(include={"transactions"}),
        media_type="application/json",
        headers={"Content-Disposition": _content_disposition(filename_base, "json")},
    )
