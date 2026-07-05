from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.model import Revenue
from app.budget.schema import RevenueOneOffCreate, RevenueSalaireUpsert
from app.budget.service import (
    add_one_off,
    delete_one_off,
    delete_salaire_correction,
    get_effective_salary_for_period,
    get_period_summary,
    upsert_salaire,
)
from app.core.db import Base


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_budget_service.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    yield session
    session.close()


def _add_account(db, is_common=False, name="Personnel-Lui") -> Account:
    account = Account(name=name, is_common=is_common, start_day=1)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def test_upsert_salaire_creates_reference_salary(db):
    account = _add_account(db)
    revenue = upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("2500.00")),
        db,
    )
    assert revenue.kind == "salaire"
    assert revenue.period_start is None
    assert revenue.amount == Decimal("2500.00")


def test_upsert_salaire_reference_twice_updates_same_row(db):
    account = _add_account(db)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("2500.00")),
        db,
    )
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("2700.00")),
        db,
    )
    rows = db.query(Revenue).filter_by(account_id=account.account_id, kind="salaire").all()
    assert len(rows) == 1
    assert rows[0].amount == Decimal("2700.00")


def test_upsert_salaire_correction_for_period_does_not_affect_reference(db):
    account = _add_account(db)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("2500.00")),
        db,
    )
    upsert_salaire(
        RevenueSalaireUpsert(
            account_id=account.account_id, period_start=date(2026, 8, 1), amount=Decimal("1000.00")
        ),
        db,
    )
    assert get_effective_salary_for_period(account.account_id, date(2026, 8, 1), db) == Decimal("1000.00")
    assert get_effective_salary_for_period(account.account_id, date(2026, 7, 1), db) == Decimal("2500.00")


def test_get_effective_salary_for_period_returns_zero_when_nothing_defined(db):
    account = _add_account(db)
    assert get_effective_salary_for_period(account.account_id, date(2026, 7, 1), db) == Decimal("0.00")


def test_delete_salaire_correction_reverts_to_reference(db):
    account = _add_account(db)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("2500.00")),
        db,
    )
    upsert_salaire(
        RevenueSalaireUpsert(
            account_id=account.account_id, period_start=date(2026, 8, 1), amount=Decimal("1000.00")
        ),
        db,
    )
    delete_salaire_correction(account.account_id, date(2026, 8, 1), db)
    assert get_effective_salary_for_period(account.account_id, date(2026, 8, 1), db) == Decimal("2500.00")


def test_delete_salaire_correction_raises_404_when_none_exists(db):
    account = _add_account(db)
    with pytest.raises(HTTPException) as exc_info:
        delete_salaire_correction(account.account_id, date(2026, 8, 1), db)
    assert exc_info.value.status_code == 404


def test_add_and_delete_one_off(db):
    account = _add_account(db)
    revenue = add_one_off(
        RevenueOneOffCreate(
            account_id=account.account_id,
            period_start=date(2026, 7, 1),
            amount=Decimal("300.00"),
            description="Prime",
        ),
        db,
    )
    assert revenue.kind == "ponctuel"
    assert revenue.description == "Prime"

    delete_one_off(revenue.revenue_id, db)
    assert db.get(Revenue, revenue.revenue_id) is None


def test_delete_one_off_raises_404_when_not_found(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_one_off(999, db)
    assert exc_info.value.status_code == 404


def test_get_period_summary_aggregates_salary_and_one_off(db):
    account = _add_account(db)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("2500.00")),
        db,
    )
    add_one_off(
        RevenueOneOffCreate(
            account_id=account.account_id,
            period_start=date(2026, 7, 1),
            amount=Decimal("300.00"),
            description="Prime",
        ),
        db,
    )
    add_one_off(
        RevenueOneOffCreate(
            account_id=account.account_id,
            period_start=date(2026, 7, 1),
            amount=Decimal("50.00"),
            description="Remboursement",
        ),
        db,
    )

    summary = get_period_summary(account.account_id, date(2026, 7, 1), db)

    assert summary.reference_amount == Decimal("2500.00")
    assert summary.effective_salary == Decimal("2500.00")
    assert summary.has_correction is False
    assert len(summary.one_off) == 2
    assert summary.total == Decimal("2850.00")


def test_get_period_summary_reflects_correction_and_flag(db):
    account = _add_account(db)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("2500.00")),
        db,
    )
    upsert_salaire(
        RevenueSalaireUpsert(
            account_id=account.account_id, period_start=date(2026, 8, 1), amount=Decimal("1000.00")
        ),
        db,
    )

    summary = get_period_summary(account.account_id, date(2026, 8, 1), db)

    assert summary.has_correction is True
    assert summary.effective_salary == Decimal("1000.00")
    assert summary.reference_amount == Decimal("2500.00")
    assert summary.total == Decimal("1000.00")


@pytest.mark.parametrize(
    "call",
    [
        lambda account_id, db: upsert_salaire(
            RevenueSalaireUpsert(account_id=account_id, period_start=None, amount=Decimal("100.00")), db
        ),
        lambda account_id, db: get_period_summary(account_id, date(2026, 7, 1), db),
        lambda account_id, db: delete_salaire_correction(account_id, date(2026, 7, 1), db),
        lambda account_id, db: add_one_off(
            RevenueOneOffCreate(
                account_id=account_id, period_start=date(2026, 7, 1), amount=Decimal("10.00"), description="x"
            ),
            db,
        ),
    ],
)
def test_common_account_is_rejected_with_422(db, call):
    account = _add_account(db, is_common=True, name="Commun")
    with pytest.raises(HTTPException) as exc_info:
        call(account.account_id, db)
    assert exc_info.value.status_code == 422


def test_unknown_account_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        upsert_salaire(
            RevenueSalaireUpsert(account_id=999, period_start=None, amount=Decimal("100.00")), db
        )
    assert exc_info.value.status_code == 404
