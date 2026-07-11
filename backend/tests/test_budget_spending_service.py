from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.service import get_tag_spending
from app.core.db import Base
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_budget_spending_service.db"
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


def _current_period_start(today: date) -> date:
    return date(today.year, today.month, 1)


def test_simple_expense_on_personal_account_is_visible(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    _add_expense(db, account, tag, Decimal("-42.00"), today)

    result = get_tag_spending(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("42.00")
    assert row.tag_name == tag.name
    assert row.parent_id is None
    assert row.level == tag.level


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

    result = get_tag_spending(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[child.tag_id].spent == Decimal("10.00")
    assert by_id[parent.tag_id].spent == Decimal("30.00")
    assert by_id[grandparent.tag_id].spent == Decimal("35.00")


def test_hierarchy_two_levels_parent_immediately_followed_by_children(db):
    account = _add_account(db, is_common=True, name="Commun")
    parent = _add_tag(db, name="Charges", level=1)
    fixes = _add_tag(db, name="Fixes", parent_id=parent.tag_id, level=2)
    variables = _add_tag(db, name="Variables", parent_id=parent.tag_id, level=2)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, fixes, Decimal("-10.00"), today)
    _add_expense(db, account, variables, Decimal("-5.00"), today)

    result = get_tag_spending(account.account_id, period_start, db)
    order = [r.tag_id for r in result]

    parent_index = order.index(parent.tag_id)
    # Ordre exact (pas seulement l'ensemble) : les frères sont triés par tag_id
    # croissant, ordre de création ici puisque `fixes` a été créé avant `variables`.
    assert order[parent_index + 1 : parent_index + 3] == [fixes.tag_id, variables.tag_id]


def test_two_independent_root_groups_keep_stable_order(db):
    account = _add_account(db, is_common=True, name="Commun")
    alimentation = _add_tag(db, name="Alimentation", level=1)
    loisirs = _add_tag(db, name="Loisirs", level=1)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, alimentation, Decimal("-10.00"), today)
    _add_expense(db, account, loisirs, Decimal("-20.00"), today)

    result = get_tag_spending(account.account_id, period_start, db)
    order = [r.tag_id for r in result]

    assert order.index(alimentation.tag_id) < order.index(loisirs.tag_id)


def test_three_level_hierarchy_order_is_depth_first(db):
    account = _add_account(db, is_common=True, name="Commun")
    grandparent = _add_tag(db, name="Vie quotidienne", level=1)
    parent = _add_tag(db, name="Alimentation", parent_id=grandparent.tag_id, level=2)
    child = _add_tag(db, name="Restaurant", parent_id=parent.tag_id, level=3)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, grandparent, Decimal("-5.00"), today)
    _add_expense(db, account, parent, Decimal("-20.00"), today)
    _add_expense(db, account, child, Decimal("-10.00"), today)

    result = get_tag_spending(account.account_id, period_start, db)
    order = [r.tag_id for r in result]

    assert order == [grandparent.tag_id, parent.tag_id, child.tag_id]


def test_common_account_is_accepted_and_has_no_target_fields(db):
    account = _add_account(db, is_common=True, name="Commun")
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    _add_expense(db, account, tag, Decimal("-64.20"), today)

    result = get_tag_spending(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("64.20")
    assert not hasattr(row, "target_amount")
    assert not hasattr(row, "gap")
    assert not hasattr(row, "projection")


def test_unknown_account_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        get_tag_spending(999, date.today(), db)
    assert exc_info.value.status_code == 404


def test_tag_with_zero_spend_is_absent(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    # Un autre tag porte une dépense, mais `tag` lui-même n'a aucune transaction.
    other_tag = _add_tag(db, name="Loisirs")
    _add_expense(db, account, other_tag, Decimal("-10.00"), today)

    result = get_tag_spending(account.account_id, period_start, db)

    assert all(r.tag_id != tag.tag_id for r in result)
