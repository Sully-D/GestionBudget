from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.projections.rapprochement import propose_if_match
from app.transactions.schema import (
    TransactionCreate,
    TransactionRead,
    TransactionTagCreate,
    TransactionUpdate,
)
from app.transactions.service import (
    add_tag_to_transaction,
    count_transactions_for_tag,
    create_transaction,
    delete_transaction,
    get_transaction,
    list_transactions,
    remove_tag_from_transaction,
    update_transaction,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])

# Le chemin frontend `/transactions` (liste, Task 4) collide avec ce chemin API
# GET `/transactions` : `app.frontend()` ne sert les fichiers statiques qu'en
# dernier recours, jamais avant une route FastAPI existante (cf. sa docstring).
# Une navigation directe/rafraîchissement du navigateur sur `/transactions` sans
# `account_id` doit donc être détectée ici et servie comme la page HTML de la
# SPA, plutôt que de renvoyer l'erreur 422 destinée aux appels API/tests
# (qui n'envoient pas `Accept: text/html`).
FRONTEND_INDEX = Path(settings.frontend_dist_dir) / "index.html"


def _prefers_html(accept_header: str) -> bool:
    # Une vraie navigation navigateur liste `text/html` en tête (ex.
    # "text/html,application/xhtml+xml,..."). Ne vérifier que le premier
    # type média évite qu'un client API envoyant "application/json,
    # text/html;q=0.1" (text/html présent mais en dernier recours) reçoive
    # la SPA au lieu du JSON attendu.
    first = accept_header.split(",")[0].strip()
    return first.startswith("text/html")


@router.get("")
def get_transactions(
    request: Request,
    account_id: int | None = Query(default=None),
    reference_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if account_id is None:
        if _prefers_html(request.headers.get("accept", "")):
            if not FRONTEND_INDEX.exists():
                raise HTTPException(status_code=404, detail="Frontend introuvable")
            return FileResponse(FRONTEND_INDEX)
        raise HTTPException(status_code=422, detail="account_id: Field required")

    period_start, period_end, transactions = list_transactions(
        account_id, reference_date, db
    )
    return {
        "data": {
            "period_start": period_start,
            "period_end": period_end,
            "transactions": [
                TransactionRead.model_validate(t) for t in transactions
            ],
        }
    }


@router.post("")
def post_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    transaction = create_transaction(payload, db)
    propose_if_match(transaction.transaction_id, db)
    return {"data": TransactionRead.model_validate(transaction)}


@router.get("/tags/{tag_id:int}/count")
def get_tag_usage_count(tag_id: int, db: Session = Depends(get_db)):
    return {"data": {"count": count_transactions_for_tag(tag_id, db)}}


# Convertisseur de chemin Starlette `:int` explicite (pas seulement l'annotation
# Python `transaction_id: int`) : le frontend a une route `/transactions/nouvelle`
# de même arité que `/transactions/{transaction_id}`. Sans `:int` dans le pattern,
# Starlette route "nouvelle" vers ces path operations (le matching structurel
# réussit avant la validation Pydantic), qui échouent alors en 422 au lieu de
# retomber sur `app.frontend()`. Avec `:int` dans le pattern, un segment non
# numérique ne matche pas la route au niveau du routage lui-même, et Starlette
# continue vers `app.frontend()` qui sert la SPA — aucune négociation `Accept`
# n'est nécessaire ici, contrairement à `GET /transactions` ci-dessus.
@router.get("/{transaction_id:int}")
def get_transaction_by_id(transaction_id: int, db: Session = Depends(get_db)):
    transaction = get_transaction(transaction_id, db)
    return {"data": TransactionRead.model_validate(transaction)}


@router.put("/{transaction_id:int}")
def put_transaction(
    transaction_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)
):
    transaction = update_transaction(transaction_id, payload, db)
    return {"data": TransactionRead.model_validate(transaction)}


@router.delete("/{transaction_id:int}")
def delete_transaction_endpoint(transaction_id: int, db: Session = Depends(get_db)):
    delete_transaction(transaction_id, db)
    return {"data": None}


@router.post("/{transaction_id:int}/tags")
def post_transaction_tag(
    transaction_id: int, payload: TransactionTagCreate, db: Session = Depends(get_db)
):
    transaction = add_tag_to_transaction(transaction_id, payload.tag_id, db)
    return {"data": TransactionRead.model_validate(transaction)}


@router.delete("/{transaction_id:int}/tags/{tag_id:int}")
def delete_transaction_tag(
    transaction_id: int, tag_id: int, db: Session = Depends(get_db)
):
    remove_tag_from_transaction(transaction_id, tag_id, db)
    return {"data": None}
