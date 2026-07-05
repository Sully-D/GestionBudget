from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.model import BudgetTarget
from app.budget.schema import BudgetTargetUpsert
from app.budget.service import delete_budget_target, get_budget_targets, upsert_budget_target
from app.core.db import Base
from app.tags.model import Tag


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_budget_targets_service.db"
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


def _add_tag(db, name="Alimentation", parent_id=None, level=1) -> Tag:
    tag = Tag(name=name, parent_id=parent_id, level=level)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def test_upsert_budget_target_creates_target(db):
    account = _add_account(db)
    tag = _add_tag(db)
    target = upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("15.00")),
        db,
    )
    assert target.percentage == Decimal("15.00")
    assert target.account_id == account.account_id
    assert target.tag_id == tag.tag_id


def test_upsert_budget_target_twice_updates_same_row(db):
    account = _add_account(db)
    tag = _add_tag(db)
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("15.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )
    rows = db.query(BudgetTarget).filter_by(account_id=account.account_id, tag_id=tag.tag_id).all()
    assert len(rows) == 1
    assert rows[0].percentage == Decimal("20.00")


def test_upsert_budget_target_unknown_tag_returns_404(db):
    account = _add_account(db)
    with pytest.raises(HTTPException) as exc_info:
        upsert_budget_target(
            BudgetTargetUpsert(account_id=account.account_id, tag_id=999, percentage=Decimal("15.00")),
            db,
        )
    assert exc_info.value.status_code == 404


def test_upsert_budget_target_unknown_account_returns_404(db):
    tag = _add_tag(db)
    with pytest.raises(HTTPException) as exc_info:
        upsert_budget_target(
            BudgetTargetUpsert(account_id=999, tag_id=tag.tag_id, percentage=Decimal("15.00")),
            db,
        )
    assert exc_info.value.status_code == 404


def test_upsert_budget_target_on_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    tag = _add_tag(db)
    with pytest.raises(HTTPException) as exc_info:
        upsert_budget_target(
            BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("15.00")),
            db,
        )
    assert exc_info.value.status_code == 422


def test_delete_budget_target_removes_row(db):
    account = _add_account(db)
    tag = _add_tag(db)
    target = upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("15.00")),
        db,
    )
    delete_budget_target(target.target_id, db)
    assert db.get(BudgetTarget, target.target_id) is None


def test_delete_budget_target_unknown_id_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_budget_target(999, db)
    assert exc_info.value.status_code == 404


def test_get_budget_targets_filters_by_account(db):
    account_a = _add_account(db, name="Personnel-Lui")
    account_b = _add_account(db, name="Personnel-Elle")
    tag = _add_tag(db)
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account_a.account_id, tag_id=tag.tag_id, percentage=Decimal("15.00")),
        db,
    )
    targets_a = get_budget_targets(account_a.account_id, db)
    targets_b = get_budget_targets(account_b.account_id, db)
    assert len(targets_a) == 1
    assert targets_b == []


def test_get_budget_targets_on_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    with pytest.raises(HTTPException) as exc_info:
        get_budget_targets(account.account_id, db)
    assert exc_info.value.status_code == 422
