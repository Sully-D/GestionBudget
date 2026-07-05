from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.schema import BudgetTargetUpsert, RevenueSalaireUpsert
from app.budget.service import get_tag_tracking, upsert_budget_target, upsert_salaire
from app.core.db import Base
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_budget_tracking_service.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
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


def _add_tag(db, name="Alimentation", parent_id=None, level=1) -> Tag:
    tag = Tag(name=name, parent_id=parent_id, level=level)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _add_expense(db, account, tag, amount, tx_date) -> Transaction:
    tx = Transaction(
        account_id=account.account_id,
        date=tx_date,
        amount=amount,
        label="Dépense",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag.tag_id))
    db.commit()
    return tx


def _add_expense_multi_tag(db, account, tags, amount, tx_date) -> Transaction:
    tx = Transaction(
        account_id=account.account_id,
        date=tx_date,
        amount=amount,
        label="Dépense",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    for tag in tags:
        db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag.tag_id))
    db.commit()
    return tx


def _current_period_start(today: date) -> date:
    return date(today.year, today.month, 1)


def test_tag_with_target_and_spending_below_target_has_positive_gap(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )
    _add_expense(db, account, tag, Decimal("-150.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("150.00")
    assert row.target_amount == Decimal("200.00")
    assert row.gap == Decimal("50.00")
    assert row.projection is not None


def test_tag_with_target_and_overspend_has_negative_gap(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )
    _add_expense(db, account, tag, Decimal("-300.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.target_amount == Decimal("200.00")
    assert row.gap == Decimal("-100.00")


def test_tag_without_target_has_only_spent(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    _add_expense(db, account, tag, Decimal("-42.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("42.00")
    assert row.target_percentage is None
    assert row.target_amount is None
    assert row.gap is None
    assert row.projection is None


def test_parent_aggregates_direct_plus_children_three_levels(db):
    account = _add_account(db)
    grandparent = _add_tag(db, name="Vie quotidienne", level=1)
    parent = _add_tag(db, name="Alimentation", parent_id=grandparent.tag_id, level=2)
    child = _add_tag(db, name="Restaurant", parent_id=parent.tag_id, level=3)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, grandparent, Decimal("-5.00"), today)
    _add_expense(db, account, parent, Decimal("-20.00"), today)
    _add_expense(db, account, child, Decimal("-10.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[child.tag_id].spent == Decimal("10.00")
    assert by_id[parent.tag_id].spent == Decimal("30.00")
    assert by_id[grandparent.tag_id].spent == Decimal("35.00")


def test_past_period_has_no_projection_even_with_target(db):
    account = _add_account(db)
    tag = _add_tag(db)
    past_period_start = date(1999, 1, 1)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )
    _add_expense(db, account, tag, Decimal("-150.00"), date(1999, 1, 10))

    result = get_tag_tracking(account.account_id, past_period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("150.00")
    assert row.target_amount == Decimal("200.00")
    assert row.gap == Decimal("50.00")
    assert row.projection is None


def test_tag_with_target_and_zero_spend_is_visible(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )

    result = get_tag_tracking(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("0.00")
    assert row.target_amount == Decimal("200.00")
    assert row.projection == Decimal("0.00")


def test_transaction_tagged_with_both_ancestor_and_descendant_counts_once(db):
    account = _add_account(db)
    parent = _add_tag(db, name="Alimentation", level=1)
    child = _add_tag(db, name="Restaurant", parent_id=parent.tag_id, level=2)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense_multi_tag(db, account, [parent, child], Decimal("-40.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[parent.tag_id].spent == Decimal("40.00")
    assert by_id[child.tag_id].spent == Decimal("40.00")


def test_target_referencing_deleted_tag_is_ignored(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )
    # Simule un tag supprimé alors qu'une Cible le référence encore (delete_tag
    # ne garde-fou pas contre ce cas et SQLite n'impose pas les FK par défaut).
    db.query(Tag).filter(Tag.tag_id == tag.tag_id).delete()
    db.commit()

    result = get_tag_tracking(account.account_id, period_start, db)

    assert all(r.tag_id != tag.tag_id for r in result)


def test_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    with pytest.raises(HTTPException) as exc_info:
        get_tag_tracking(account.account_id, date.today(), db)
    assert exc_info.value.status_code == 422


def test_unknown_account_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        get_tag_tracking(999, date.today(), db)
    assert exc_info.value.status_code == 404
