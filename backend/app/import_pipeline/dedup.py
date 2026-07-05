from sqlalchemy.orm import Session

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
