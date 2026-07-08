from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.accounts.service import compute_balance, compute_period
from app.core.db import Base
from app.transactions.model import Transaction


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_accounts_service.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    yield session
    session.close()


def _add_account(db, **kwargs) -> Account:
    account = Account(name="Test", is_common=False, start_day=1, **kwargs)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def test_compute_balance_returns_zero_when_no_reference_balance_and_no_transactions(db):
    account = _add_account(db, reference_balance=None)
    assert compute_balance(account, db) == Decimal("0.00")


def test_compute_balance_returns_reference_balance_when_defined_and_no_transactions(db):
    account = _add_account(
        db, reference_balance=Decimal("847.00"), reference_date=date(2026, 7, 1)
    )
    assert compute_balance(account, db) == Decimal("847.00")


def test_compute_balance_adds_transactions_from_reference_date_inclusive(db):
    account = _add_account(
        db, reference_balance=Decimal("100.00"), reference_date=date(2026, 7, 5)
    )
    db.add_all(
        [
            Transaction(
                account_id=account.account_id,
                date=date(2026, 7, 4),
                amount=Decimal("-1000.00"),
                label="Avant la référence, exclue",
            ),
            Transaction(
                account_id=account.account_id,
                date=date(2026, 7, 5),
                amount=Decimal("-20.00"),
                label="Le jour même, incluse",
            ),
            Transaction(
                account_id=account.account_id,
                date=date(2026, 7, 6),
                amount=Decimal("50.00"),
                label="Après la référence, incluse",
            ),
        ]
    )
    db.commit()
    assert compute_balance(account, db) == Decimal("130.00")


def test_compute_balance_sums_all_transactions_when_no_reference(db):
    account = _add_account(db, reference_balance=None, reference_date=None)
    db.add_all(
        [
            Transaction(
                account_id=account.account_id,
                date=date(2020, 1, 1),
                amount=Decimal("-30.00"),
                label="Ancienne",
            ),
            Transaction(
                account_id=account.account_id,
                date=date(2026, 7, 6),
                amount=Decimal("10.00"),
                label="Récente",
            ),
        ]
    )
    db.commit()
    assert compute_balance(account, db) == Decimal("-20.00")


def test_compute_period_delegates_to_period_for():
    account = Account(name="Test", is_common=False, start_day=15)
    assert compute_period(account, date(2026, 7, 20)) == (
        date(2026, 7, 15),
        date(2026, 8, 14),
    )


def test_compute_period_defaults_to_today_when_no_reference_date_given():
    account = Account(name="Test", is_common=False, start_day=1)
    period_start, period_end = compute_period(account)
    today = date.today()
    assert period_start <= today <= period_end


def test_compute_balance_as_of_date_excludes_transactions_after_it(db):
    account = _add_account(
        db, reference_balance=Decimal("100.00"), reference_date=date(2026, 6, 25)
    )
    db.add_all(
        [
            Transaction(
                account_id=account.account_id,
                date=date(2026, 6, 30),
                amount=Decimal("-20.00"),
                label="Incluse",
            ),
            Transaction(
                account_id=account.account_id,
                date=date(2026, 7, 10),
                amount=Decimal("-1000.00"),
                label="Après as_of_date, exclue",
            ),
        ]
    )
    db.commit()
    assert compute_balance(account, db, as_of_date=date(2026, 7, 5)) == Decimal("80.00")


def test_compute_balance_as_of_date_inclusive_of_matching_date(db):
    account = _add_account(
        db, reference_balance=Decimal("0.00"), reference_date=date(2026, 7, 1)
    )
    db.add(
        Transaction(
            account_id=account.account_id,
            date=date(2026, 7, 5),
            amount=Decimal("-20.00"),
            label="Le jour même de as_of_date, incluse",
        )
    )
    db.commit()
    assert compute_balance(account, db, as_of_date=date(2026, 7, 5)) == Decimal("-20.00")


def test_compute_balance_as_of_date_none_matches_unbounded_behaviour(db):
    account = _add_account(
        db, reference_balance=Decimal("100.00"), reference_date=date(2026, 7, 5)
    )
    db.add_all(
        [
            Transaction(
                account_id=account.account_id,
                date=date(2026, 7, 4),
                amount=Decimal("-1000.00"),
                label="Avant la référence, exclue",
            ),
            Transaction(
                account_id=account.account_id,
                date=date(2026, 7, 6),
                amount=Decimal("50.00"),
                label="Après la référence, incluse",
            ),
        ]
    )
    db.commit()
    assert compute_balance(account, db, as_of_date=None) == compute_balance(account, db)
