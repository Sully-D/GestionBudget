from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.core.period import period_for
from app.projections.model import PlannedExpense
from app.projections.schema import (
    PlannedExpenseSimpleCreate,
    PlannedExpenseSplitCreate,
    PlannedExpenseUpdate,
)
from app.projections.service import (
    create_planned_expense,
    create_planned_expense_split,
    delete_planned_expense,
    list_planned_expenses,
    update_planned_expense,
)
from app.tags.model import Tag


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_planned_expenses_service.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    yield session
    session.close()


def _add_account(db, is_common=False, name="Personnel-Lui", start_day=1) -> Account:
    account = Account(name=name, is_common=is_common, start_day=start_day)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _add_tag(db, name="Loisirs", parent_id=None, level=1) -> Tag:
    tag = Tag(name=name, parent_id=parent_id, level=level)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def test_create_planned_expense_simple_creates_row_with_no_series(db):
    account = _add_account(db)
    tag = _add_tag(db)
    planned_expense = create_planned_expense(
        PlannedExpenseSimpleCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            date=date(2026, 8, 15),
            amount=Decimal("-120.00"),
            description="Vacances",
        ),
        db,
    )
    assert planned_expense.series_id is None
    assert planned_expense.period_index is None
    assert planned_expense.total_periods is None
    assert planned_expense.amount == Decimal("-120.00")


def test_create_planned_expense_split_creates_n_rows_with_shared_series(db):
    account = _add_account(db, start_day=1)
    tag = _add_tag(db)
    planned_expenses = create_planned_expense_split(
        PlannedExpenseSplitCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            start_date=date(2026, 1, 10),
            total_amount=Decimal("300.00"),
            total_periods=3,
            description="Vacances ventilées",
        ),
        db,
    )
    assert len(planned_expenses) == 3
    series_ids = {p.series_id for p in planned_expenses}
    assert len(series_ids) == 1
    assert [p.period_index for p in planned_expenses] == [1, 2, 3]
    assert all(p.total_periods == 3 for p in planned_expenses)

    expected_dates = [
        period_for(1, date(2026, 1, 10))[0],
        period_for(1, date(2026, 2, 1))[0],
        period_for(1, date(2026, 3, 1))[0],
    ]
    assert [p.date for p in planned_expenses] == expected_dates
    assert sum((p.amount for p in planned_expenses), Decimal("0")) == Decimal("-300.00")


def test_create_planned_expense_split_remainder_on_last_fraction(db):
    account = _add_account(db)
    tag = _add_tag(db)
    planned_expenses = create_planned_expense_split(
        PlannedExpenseSplitCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            start_date=date(2026, 1, 10),
            total_amount=Decimal("100.00"),
            total_periods=3,
            description="Reste",
        ),
        db,
    )
    amounts = [p.amount for p in planned_expenses]
    assert amounts[0] == Decimal("-33.33")
    assert amounts[1] == Decimal("-33.33")
    assert amounts[2] == Decimal("-33.34")
    assert sum(amounts, Decimal("0")) == Decimal("-100.00")


def test_create_planned_expense_split_tiny_amount_returns_422(db):
    account = _add_account(db)
    tag = _add_tag(db)
    with pytest.raises(HTTPException) as exc_info:
        create_planned_expense_split(
            PlannedExpenseSplitCreate(
                account_id=account.account_id,
                tag_id=tag.tag_id,
                start_date=date(2026, 1, 10),
                total_amount=Decimal("0.01"),
                total_periods=60,
                description="Trop faible",
            ),
            db,
        )
    assert exc_info.value.status_code == 422


def test_delete_planned_expense_simple_removes_only_that_row(db):
    account = _add_account(db)
    tag = _add_tag(db)
    simple = create_planned_expense(
        PlannedExpenseSimpleCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            date=date(2026, 8, 15),
            amount=Decimal("-50.00"),
            description="Cadeau",
        ),
        db,
    )
    other = create_planned_expense(
        PlannedExpenseSimpleCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            date=date(2026, 9, 15),
            amount=Decimal("-60.00"),
            description="Autre",
        ),
        db,
    )
    delete_planned_expense(simple.expense_id, db)
    assert db.get(PlannedExpense, simple.expense_id) is None
    assert db.get(PlannedExpense, other.expense_id) is not None


def test_delete_planned_expense_belonging_to_series_removes_all_rows(db):
    account = _add_account(db)
    tag = _add_tag(db)
    planned_expenses = create_planned_expense_split(
        PlannedExpenseSplitCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            start_date=date(2026, 1, 10),
            total_amount=Decimal("300.00"),
            total_periods=3,
            description="Série",
        ),
        db,
    )
    delete_planned_expense(planned_expenses[0].expense_id, db)
    remaining = db.query(PlannedExpense).all()
    assert remaining == []


def test_update_planned_expense_simple_and_series_fraction_work_identically(db):
    account = _add_account(db)
    tag = _add_tag(db)
    other_tag = _add_tag(db, name="Autre", level=1)

    simple = create_planned_expense(
        PlannedExpenseSimpleCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            date=date(2026, 8, 15),
            amount=Decimal("-50.00"),
            description="Cadeau",
        ),
        db,
    )
    updated_simple = update_planned_expense(
        simple.expense_id,
        PlannedExpenseUpdate(
            date=date(2026, 8, 20),
            amount=Decimal("-55.00"),
            tag_id=other_tag.tag_id,
            description="Cadeau modifié",
        ),
        db,
    )
    assert updated_simple.date == date(2026, 8, 20)
    assert updated_simple.amount == Decimal("-55.00")
    assert updated_simple.tag_id == other_tag.tag_id
    assert updated_simple.description == "Cadeau modifié"

    planned_expenses = create_planned_expense_split(
        PlannedExpenseSplitCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            start_date=date(2026, 1, 10),
            total_amount=Decimal("300.00"),
            total_periods=3,
            description="Série",
        ),
        db,
    )
    fraction = planned_expenses[1]
    updated_fraction = update_planned_expense(
        fraction.expense_id,
        PlannedExpenseUpdate(
            date=date(2026, 3, 1),
            amount=Decimal("-99.00"),
            tag_id=other_tag.tag_id,
            description="Fraction modifiée",
        ),
        db,
    )
    assert updated_fraction.date == date(2026, 3, 1)
    assert updated_fraction.amount == Decimal("-99.00")
    assert updated_fraction.series_id == fraction.series_id


def test_list_planned_expenses_sorted_by_date_then_expense_id(db):
    account = _add_account(db)
    tag = _add_tag(db)
    create_planned_expense(
        PlannedExpenseSimpleCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            date=date(2026, 9, 1),
            amount=Decimal("-10.00"),
            description="B",
        ),
        db,
    )
    create_planned_expense(
        PlannedExpenseSimpleCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            date=date(2026, 8, 1),
            amount=Decimal("-10.00"),
            description="A",
        ),
        db,
    )
    result = list_planned_expenses(account.account_id, db)
    assert [p.description for p in result] == ["A", "B"]


def test_create_planned_expense_on_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    tag = _add_tag(db)
    with pytest.raises(HTTPException) as exc_info:
        create_planned_expense(
            PlannedExpenseSimpleCreate(
                account_id=account.account_id,
                tag_id=tag.tag_id,
                date=date(2026, 8, 15),
                amount=Decimal("-10.00"),
                description="X",
            ),
            db,
        )
    assert exc_info.value.status_code == 422


def test_create_planned_expense_unknown_tag_returns_404(db):
    account = _add_account(db)
    with pytest.raises(HTTPException) as exc_info:
        create_planned_expense(
            PlannedExpenseSimpleCreate(
                account_id=account.account_id,
                tag_id=999,
                date=date(2026, 8, 15),
                amount=Decimal("-10.00"),
                description="X",
            ),
            db,
        )
    assert exc_info.value.status_code == 404


def test_create_planned_expense_unknown_account_returns_404(db):
    tag = _add_tag(db)
    with pytest.raises(HTTPException) as exc_info:
        create_planned_expense(
            PlannedExpenseSimpleCreate(
                account_id=999,
                tag_id=tag.tag_id,
                date=date(2026, 8, 15),
                amount=Decimal("-10.00"),
                description="X",
            ),
            db,
        )
    assert exc_info.value.status_code == 404


def test_update_planned_expense_unknown_id_returns_404(db):
    tag = _add_tag(db)
    with pytest.raises(HTTPException) as exc_info:
        update_planned_expense(
            999,
            PlannedExpenseUpdate(
                date=date(2026, 8, 15),
                amount=Decimal("-10.00"),
                tag_id=tag.tag_id,
                description="X",
            ),
            db,
        )
    assert exc_info.value.status_code == 404


def test_delete_planned_expense_unknown_id_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_planned_expense(999, db)
    assert exc_info.value.status_code == 404
