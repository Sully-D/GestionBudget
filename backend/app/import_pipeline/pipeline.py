from datetime import date as date_
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.import_pipeline.csv_parser import (
    ColumnMapping,
    CsvParseError,
    CsvPreview,
    compute_header_signature,
)
from app.import_pipeline.csv_parser import preview_csv as _preview_csv
from app.import_pipeline.csv_parser import parse_csv
from app.import_pipeline.dedup import split_new_and_duplicates
from app.import_pipeline.model import CsvColumnMapping
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
) -> list[int]:
    try:
        transaction_ids: list[int] = []
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
            transaction_ids.append(transaction.transaction_id)
            rule = evaluate_rules_verbose(rules, label, payee)
            if rule is not None:
                db.add(
                    TransactionTag(transaction_id=transaction.transaction_id, tag_id=rule.tag_id)
                )
        db.commit()
        return transaction_ids
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Erreur lors de l'import : aucune Transaction n'a été enregistrée.",
        ) from exc


def import_ofx(account_id: int, raw: bytes, db: Session) -> tuple[int, int, list[int]]:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")

    try:
        parsed = parse_ofx(raw)
    except OfxParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_transactions, duplicate_count = split_new_and_duplicates(parsed, account_id, db)
    rules = list_rules(db)

    transaction_ids = _persist_and_tag(
        account_id,
        [(item.date, item.amount, item.label, item.payee, item.fitid) for item in new_transactions],
        rules,
        db,
    )

    return len(new_transactions), duplicate_count, transaction_ids


def _find_saved_mapping(account_id: int, signature: str, db: Session) -> CsvColumnMapping | None:
    return (
        db.query(CsvColumnMapping)
        .filter(
            CsvColumnMapping.account_id == account_id,
            CsvColumnMapping.header_signature == signature,
        )
        .one_or_none()
    )


def preview_csv(raw: bytes, account_id: int, db: Session) -> tuple[CsvPreview, ColumnMapping | None]:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")

    try:
        preview = _preview_csv(raw)
    except CsvParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    signature = compute_header_signature(preview.columns)
    existing = _find_saved_mapping(account_id, signature, db)
    saved_mapping = (
        ColumnMapping(
            date_column=existing.date_column,
            montant_column=existing.montant_column,
            libelle_column=existing.libelle_column,
            tiers_column=existing.tiers_column,
        )
        if existing is not None
        else None
    )
    return preview, saved_mapping


def import_csv(
    account_id: int, raw: bytes, mapping: ColumnMapping, db: Session
) -> tuple[int, int, list[int]]:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")

    try:
        parsed, skipped_count = parse_csv(raw, mapping)
    except CsvParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if parsed:
        # Même fichier, donc mêmes en-têtes que ceux déjà validés par parse_csv
        # ci-dessus : cet appel ne peut pas échouer différemment.
        signature = compute_header_signature(_preview_csv(raw).columns)
        # Upsert atomique (ON CONFLICT) plutôt qu'un lookup-puis-insert/update :
        # deux imports concurrents pour le même (account_id, header_signature)
        # ne doivent jamais se heurter à une violation de contrainte unique.
        # Mémorisé uniquement si au moins une ligne a été importée avec succès
        # -- un mappage qui ne produit que des lignes ignorées ne doit pas
        # écraser un mappage mémorisé qui fonctionnait.
        stmt = sqlite_insert(CsvColumnMapping).values(
            account_id=account_id,
            header_signature=signature,
            date_column=mapping.date_column,
            montant_column=mapping.montant_column,
            libelle_column=mapping.libelle_column,
            tiers_column=mapping.tiers_column,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[CsvColumnMapping.account_id, CsvColumnMapping.header_signature],
            set_={
                "date_column": mapping.date_column,
                "montant_column": mapping.montant_column,
                "libelle_column": mapping.libelle_column,
                "tiers_column": mapping.tiers_column,
            },
        )
        db.execute(stmt)

    rules = list_rules(db)

    # pas de fitid : les imports CSV n'ont pas de clé de déduplication (AC #5)
    transaction_ids = _persist_and_tag(
        account_id,
        [(item.date, item.amount, item.label, item.payee, None) for item in parsed],
        rules,
        db,
    )

    return len(parsed), skipped_count, transaction_ids
