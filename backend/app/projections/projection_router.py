from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.projections.service import get_projection

router = APIRouter(prefix="/projection", tags=["projections"])

# Le chemin frontend `/projection` (Task 6) collide avec ce chemin API
# GET `/projection` : `app.frontend()` ne sert les fichiers statiques qu'en
# dernier recours, jamais avant une route FastAPI existante (cf. sa docstring).
# Une navigation directe/rafraîchissement du navigateur sur `/projection` sans
# `account_id` doit donc être détectée ici et servie comme la page HTML de la
# SPA, plutôt que de renvoyer l'erreur 422 destinée aux appels API/tests
# (qui n'envoient pas `Accept: text/html`) — même pattern que
# `transactions/router.py::get_transactions`.
FRONTEND_INDEX = Path(settings.frontend_dist_dir) / "index.html"


def _prefers_html(accept_header: str) -> bool:
    first = accept_header.split(",")[0].strip()
    return first.startswith("text/html")


# Les paramètres de requête arrivent en str ; Literal[int, ...] ne coerce pas
# automatiquement (contrairement à `int` nu), d'où la conversion explicite.
# Le défaut doit rester hors de l'Annotated (et non dans Query()) pour que
# BeforeValidator s'applique bien à la valeur transmise par le client.
HorizonMonths = Annotated[Literal[1, 3, 6], BeforeValidator(int), Query()]


@router.get("")
def get_projection_endpoint(
    request: Request,
    account_id: int | None = Query(default=None),
    horizon_months: HorizonMonths = 3,
    db: Session = Depends(get_db),
):
    if account_id is None:
        if _prefers_html(request.headers.get("accept", "")):
            if not FRONTEND_INDEX.exists():
                raise HTTPException(status_code=404, detail="Frontend introuvable")
            return FileResponse(FRONTEND_INDEX)
        raise HTTPException(status_code=422, detail="account_id: Field required")

    items = get_projection(account_id, horizon_months, db)
    return {"data": items}
