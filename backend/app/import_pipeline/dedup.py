from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.import_pipeline.csv_parser import ColumnMapping, ParsedCsvTransaction
from app.import_pipeline.ofx_parser import ParsedTransaction
from app.transactions.model import Transaction


def split_new_and_duplicates(
    parsed: list[ParsedTransaction], account_id: int, db: Session
) -> tuple[list[ParsedTransaction], int]:
    existing_fitids = {
        row[0]
        for row in db.query(Transaction.fitid)
        .filter(Transaction.account_id == account_id, Transaction.fitid.isnot(None))
        .all()
    }
    new_transactions: list[ParsedTransaction] = []
    seen: set[str] = set()
    duplicate_count = 0
    for item in parsed:
        if item.fitid in existing_fitids or item.fitid in seen:
            duplicate_count += 1
            continue
        seen.add(item.fitid)
        new_transactions.append(item)
    return new_transactions, duplicate_count


RowDecision = Literal["import", "ignore"]


@dataclass
class AmbiguousCsvRow:
    row_index: int
    date: date
    amount: Decimal
    label: str
    payee: str | None
    existing_label: str
    existing_payee: str | None


def split_csv_duplicates_and_ambiguous(
    parsed: list[ParsedCsvTransaction],
    mapping: ColumnMapping,
    account_id: int,
    db: Session,
    resolutions: dict[int, RowDecision] | None = None,
) -> tuple[list[ParsedCsvTransaction], int, list[AmbiguousCsvRow]]:
    """Classe les lignes CSV parsées en (à persister, doublons certains, ambiguës en attente).

    `row_index` = position 0-based dans `parsed`, utilisée comme clé de
    corrélation stateless avec `resolutions` fourni par un appel HTTP suivant
    (cf. Boundaries du spec -- pas de nouvelle table pour l'état de revue).
    """
    resolutions = resolutions or {}
    compare_payee = mapping.tiers_column is not None

    existing_by_key: dict[tuple[date, Decimal], list[tuple[str, str | None]]] = {}
    for exist_date, exist_amount, exist_label, exist_payee in (
        db.query(Transaction.date, Transaction.amount, Transaction.label, Transaction.payee)
        .filter(Transaction.account_id == account_id)
        .order_by(Transaction.transaction_id)
        .all()
    ):
        existing_by_key.setdefault((exist_date, exist_amount), []).append((exist_label, exist_payee))

    def is_exact_match(label: str, payee: str | None, candidates: list[tuple[str, str | None]]) -> bool:
        for cand_label, cand_payee in candidates:
            if cand_label != label:
                continue
            if compare_payee and cand_payee != payee:
                continue
            return True
        return False

    to_persist: list[ParsedCsvTransaction] = []
    duplicate_count = 0
    pending: list[AmbiguousCsvRow] = []

    for row_index, item in enumerate(parsed):
        key = (item.date, item.amount)
        candidates = existing_by_key.get(key, [])

        # Une résolution explicite de l'utilisateur prime toujours sur la
        # reclassification automatique -- vérifiée AVANT is_exact_match pour
        # qu'une ligne "import" déjà appliquée plus haut (et donc ajoutée à
        # existing_by_key ci-dessous) ne puisse jamais faire passer une autre
        # ligne "import" identique pour un doublon certain (cf. AC "seules les
        # lignes marquées importer sont persistées", sans exception).
        decision = resolutions.get(row_index)
        if decision == "ignore":
            duplicate_count += 1
            continue
        if decision == "import":
            to_persist.append(item)
            existing_by_key.setdefault(key, []).append((item.label, item.payee))
            continue

        if is_exact_match(item.label, item.payee, candidates):
            duplicate_count += 1
            continue

        if candidates:
            existing_label, existing_payee = candidates[0]
            pending.append(
                AmbiguousCsvRow(
                    row_index=row_index,
                    date=item.date,
                    amount=item.amount,
                    label=item.label,
                    payee=item.payee,
                    existing_label=existing_label,
                    existing_payee=existing_payee,
                )
            )
            continue

        to_persist.append(item)
        existing_by_key.setdefault(key, []).append((item.label, item.payee))

    return to_persist, duplicate_count, pending
