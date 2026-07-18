from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.projections.rapprochement import delete_matches_for_transaction, propose_if_match
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
    search_transactions,
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
    label: str | None = Query(default=None),
    payee: str | None = Query(default=None),
    amount: Decimal | None = Query(default=None),
    amount_min: Decimal | None = Query(default=None),
    amount_max: Decimal | None = Query(default=None),
    date_exact: date | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tag_id: list[int] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if account_id is None:
        if _prefers_html(request.headers.get("accept", "")):
            if not FRONTEND_INDEX.exists():
                raise HTTPException(status_code=404, detail="Frontend introuvable")
            return FileResponse(FRONTEND_INDEX)
        raise HTTPException(status_code=422, detail="account_id: Field required")

    label = label.strip() if label else None
    payee = payee.strip() if payee else None
    has_search_filters = any(
        [
            label,
            payee,
            amount is not None,
            amount_min is not None,
            amount_max is not None,
            date_exact is not None,
            date_from is not None,
            date_to is not None,
            tag_id,
        ]
    )

    if has_search_filters:
        if amount is not None and (amount_min is not None or amount_max is not None):
            raise HTTPException(
                status_code=422,
                detail="amount ne peut pas être combiné avec amount_min/amount_max",
            )
        if date_exact is not None and (date_from is not None or date_to is not None):
            raise HTTPException(
                status_code=422,
                detail="date_exact ne peut pas être combiné avec date_from/date_to",
            )
        if (
            amount_min is not None
            and amount_max is not None
            and amount_min > amount_max
        ):
            raise HTTPException(
                status_code=422, detail="amount_min doit être inférieur ou égal à amount_max"
            )
        if date_from is not None and date_to is not None and date_from > date_to:
            raise HTTPException(
                status_code=422, detail="date_from doit être antérieure ou égale à date_to"
            )

        transactions = search_transactions(
            account_id,
            label=label,
            payee=payee,
            amount=amount,
            amount_min=amount_min,
            amount_max=amount_max,
            date_exact=date_exact,
            date_from=date_from,
            date_to=date_to,
            tag_ids=tag_id,
            db=db,
        )
        return {
            "data": {
                "period_start": None,
                "period_end": None,
                "filtered": True,
                "transactions": [
                    TransactionRead.model_validate(t) for t in transactions
                ],
            }
        }

    period_start, period_end, transactions = list_transactions(
        account_id, reference_date, db
    )
    return {
        "data": {
            "period_start": period_start,
            "period_end": period_end,
            "filtered": False,
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
    delete_matches_for_transaction(transaction_id, db)
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
