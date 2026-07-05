from datetime import date as date_
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.import_pipeline.csv_parser import ColumnMapping, CsvParseError, CsvPreview
from app.import_pipeline.csv_parser import preview_csv as _preview_csv
from app.import_pipeline.csv_parser import parse_csv
from app.import_pipeline.dedup import split_new_and_duplicates
from app.import_pipeline.ofx_parser import OfxParseError, parse_ofx
from app.tags.model import Rule
from app.tags.rule_engine.dispatcher import evaluate_rules_verbose
from app.tags.service import list_rules
from app.transactions.model import Transaction, TransactionTag


def _persist_and_tag(
    account_id: int,
    items: list[tuple[date_, Decimal, str, str | None, str | None]],
    rules: list[Rule],
    db: Session,
) -> None:
    try:
        for item_date, amount, label, payee, fitid in items:
            transaction = Transaction(
                account_id=account_id,
                date=item_date,
                amount=amount,
                label=label,
                payee=payee,
                fitid=fitid,
            )
            db.add(transaction)
            db.flush()  # obtient transaction_id sans committer — requis pour la FK de TransactionTag ci-dessous
            rule = evaluate_rules_verbose(rules, label, payee)
            if rule is not None:
                db.add(
                    TransactionTag(transaction_id=transaction.transaction_id, tag_id=rule.tag_id)
                )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Erreur lors de l'import : aucune Transaction n'a été enregistrée.",
        ) from exc


def import_ofx(account_id: int, raw: bytes, db: Session) -> tuple[int, int]:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")

    try:
        parsed = parse_ofx(raw)
    except OfxParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_transactions, duplicate_count = split_new_and_duplicates(parsed, account_id, db)
    rules = list_rules(db)

    _persist_and_tag(
        account_id,
        [(item.date, item.amount, item.label, item.payee, item.fitid) for item in new_transactions],
        rules,
        db,
    )

    return len(new_transactions), duplicate_count


def preview_csv(raw: bytes) -> CsvPreview:
    try:
        return _preview_csv(raw)
    except CsvParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def import_csv(
    account_id: int, raw: bytes, mapping: ColumnMapping, db: Session
) -> tuple[int, int]:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")

    try:
        parsed, skipped_count = parse_csv(raw, mapping)
    except CsvParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rules = list_rules(db)

    # pas de fitid : les imports CSV n'ont pas de clé de déduplication (AC #5)
    _persist_and_tag(
        account_id,
        [(item.date, item.amount, item.label, item.payee, None) for item in parsed],
        rules,
        db,
    )

    return len(parsed), skipped_count
