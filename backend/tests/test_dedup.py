from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.import_pipeline.dedup import split_new_and_duplicates
from app.import_pipeline.ofx_parser import ParsedTransaction
from app.transactions.model import Transaction


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_dedup.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    yield session
    session.close()


@pytest.fixture
def account(db):
    account = Account(name="Test", is_common=False, start_day=1)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@pytest.fixture
def other_account(db):
    account = Account(name="Autre compte", is_common=False, start_day=1)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _parsed(fitid: str, amount: str = "-10.00") -> ParsedTransaction:
    return ParsedTransaction(
        fitid=fitid,
        date=date(2026, 7, 1),
        amount=Decimal(amount),
        label="Test",
        payee="Test",
    )


def test_no_overlap_with_existing_all_become_new(db, account):
    parsed = [_parsed("FIT1"), _parsed("FIT2")]
    new_transactions, duplicate_count = split_new_and_duplicates(parsed, account.account_id, db)
    assert len(new_transactions) == 2
    assert duplicate_count == 0


def test_fitid_already_in_db_for_account_is_excluded_as_duplicate(db, account):
    db.add(
        Transaction(
            account_id=account.account_id,
            date=date(2026, 6, 1),
            amount=Decimal("-5.00"),
            label="Existant",
            fitid="FIT1",
        )
    )
    db.commit()

    parsed = [_parsed("FIT1"), _parsed("FIT2")]
    new_transactions, duplicate_count = split_new_and_duplicates(parsed, account.account_id, db)
    assert [t.fitid for t in new_transactions] == ["FIT2"]
    assert duplicate_count == 1


def test_same_fitid_on_another_account_is_not_a_duplicate(db, account, other_account):
    db.add(
        Transaction(
            account_id=other_account.account_id,
            date=date(2026, 6, 1),
            amount=Decimal("-5.00"),
            label="Existant sur un autre compte",
            fitid="FIT1",
        )
    )
    db.commit()

    parsed = [_parsed("FIT1")]
    new_transactions, duplicate_count = split_new_and_duplicates(parsed, account.account_id, db)
    assert len(new_transactions) == 1
    assert duplicate_count == 0


def test_duplicate_fitid_within_same_call_is_deduplicated(db, account):
    parsed = [_parsed("FIT1", amount="-10.00"), _parsed("FIT1", amount="-20.00")]
    new_transactions, duplicate_count = split_new_and_duplicates(parsed, account.account_id, db)
    assert len(new_transactions) == 1
    assert duplicate_count == 1
    # Vérifie explicitement laquelle des deux transactions en collision est
    # conservée (la première rencontrée), pas seulement les compteurs.
    assert new_transactions[0].amount == Decimal("-10.00")
