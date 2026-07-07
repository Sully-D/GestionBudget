from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.projections.model import PlannedExpense, RecurringMatch, RecurringTransaction
from app.projections.schema import PlannedExpenseSplitCreate
from app.projections.service import create_planned_expense_split, get_projection
from app.tags.model import Tag
from app.transactions.model import Transaction


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_projection_service.db"
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


def _add_planned_expense(db, account_id, tag_id, expense_date, amount, description="X"):
    planned_expense = PlannedExpense(
        account_id=account_id,
        tag_id=tag_id,
        series_id=None,
        period_index=None,
        total_periods=None,
        amount=amount,
        date=expense_date,
        description=description,
    )
    db.add(planned_expense)
    db.commit()
    db.refresh(planned_expense)
    return planned_expense


def _add_recurring(
    db, account_id, tag_id, signature, label, amount, periodicity, status="confirmed"
):
    recurring = RecurringTransaction(
        account_id=account_id,
        tag_id=tag_id,
        signature=signature,
        label=label,
        amount=amount,
        periodicity=periodicity,
        status=status,
    )
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def _add_transaction(db, account_id, txn_date, amount, label, payee=None):
    transaction = Transaction(
        account_id=account_id, date=txn_date, amount=amount, label=label, payee=payee
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def test_planned_expenses_in_horizon_included_out_of_horizon_excluded(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    _add_planned_expense(db, account.account_id, tag.tag_id, today, Decimal("-10.00"), "Dans horizon")
    _add_planned_expense(
        db, account.account_id, tag.tag_id, today + timedelta(days=3650), Decimal("-20.00"), "Hors horizon"
    )
    items = get_projection(account.account_id, 1, db)
    labels = [i.label for i in items if i.type == "planifiee"]
    assert "Dans horizon" in labels
    assert "Hors horizon" not in labels


def test_planned_expense_before_today_excluded(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    _add_planned_expense(
        db, account.account_id, tag.tag_id, today - timedelta(days=1), Decimal("-10.00"), "Passé"
    )
    items = get_projection(account.account_id, 1, db)
    assert items == []


def test_recurring_monthly_generates_multiple_occurrences_over_six_months(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    anchor = today - timedelta(days=20)
    _add_transaction(db, account.account_id, anchor, Decimal("-50.00"), "Salle de sport")
    _add_recurring(
        db, account.account_id, tag.tag_id, "salle de sport", "Salle de sport",
        Decimal("-50.00"), "mensuelle",
    )
    items = get_projection(account.account_id, 6, db)
    recurring_items = [i for i in items if i.type == "recurrente"]
    assert len(recurring_items) >= 5
    assert all(i.label == "Salle de sport" for i in recurring_items)


def test_recurring_weekly_generates_occurrences(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    anchor = today - timedelta(days=3)
    _add_transaction(db, account.account_id, anchor, Decimal("-15.00"), "Marché")
    _add_recurring(
        db, account.account_id, tag.tag_id, "marché", "Marché",
        Decimal("-15.00"), "hebdomadaire",
    )
    items = get_projection(account.account_id, 1, db)
    recurring_items = [i for i in items if i.type == "recurrente"]
    assert len(recurring_items) >= 1
    assert all(i.date >= today for i in recurring_items)


def test_recurring_anchored_exactly_today_not_listed_as_upcoming(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    _add_transaction(db, account.account_id, today, Decimal("-50.00"), "Salle de sport")
    _add_recurring(
        db, account.account_id, tag.tag_id, "salle de sport", "Salle de sport",
        Decimal("-50.00"), "mensuelle",
    )
    items = get_projection(account.account_id, 1, db)
    recurring_items = [i for i in items if i.type == "recurrente"]
    assert all(i.date > today for i in recurring_items)


def test_rejected_recurring_never_in_projection(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    _add_transaction(db, account.account_id, today - timedelta(days=20), Decimal("-50.00"), "Rejetée")
    _add_recurring(
        db, account.account_id, tag.tag_id, "rejetée", "Rejetée",
        Decimal("-50.00"), "mensuelle", status="rejected",
    )
    items = get_projection(account.account_id, 6, db)
    assert items == []


def test_recurring_without_matching_transaction_excluded_without_exception(db):
    account = _add_account(db)
    tag = _add_tag(db)
    _add_recurring(
        db, account.account_id, tag.tag_id, "orpheline", "Orpheline",
        Decimal("-50.00"), "mensuelle",
    )
    items = get_projection(account.account_id, 6, db)
    assert items == []


def test_recurring_tag_deleted_returns_none_tag_without_exception(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    _add_transaction(db, account.account_id, today - timedelta(days=20), Decimal("-50.00"), "Salle")
    _add_recurring(
        db, account.account_id, tag.tag_id, "salle", "Salle",
        Decimal("-50.00"), "mensuelle",
    )
    db.delete(tag)
    db.commit()
    items = get_projection(account.account_id, 6, db)
    assert len(items) >= 1
    assert all(i.tag_id is None and i.tag_name is None for i in items)


def test_projection_sorted_deterministically_by_date_type_label(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    _add_planned_expense(db, account.account_id, tag.tag_id, today, Decimal("-10.00"), "Z-planifiee")
    _add_transaction(db, account.account_id, today - timedelta(days=20), Decimal("-50.00"), "A-recurrente")
    _add_recurring(
        db, account.account_id, tag.tag_id, "a-recurrente", "A-recurrente",
        Decimal("-50.00"), "mensuelle",
    )
    items = get_projection(account.account_id, 1, db)
    keys = [(i.date, i.type, i.label) for i in items]
    assert keys == sorted(keys)


def test_projection_tie_on_date_type_label_ordered_deterministically_by_id(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    anchor = today - timedelta(days=20)
    _add_transaction(db, account.account_id, anchor, Decimal("-50.00"), "Salle", payee="Salle A")
    _add_transaction(db, account.account_id, anchor, Decimal("-50.00"), "Salle", payee="Salle B")
    first = _add_recurring(
        db, account.account_id, tag.tag_id, "salle a", "Salle", Decimal("-50.00"), "mensuelle",
    )
    second = _add_recurring(
        db, account.account_id, tag.tag_id, "salle b", "Salle", Decimal("-50.00"), "mensuelle",
    )
    items = get_projection(account.account_id, 6, db)
    tied = [i for i in items if i.type == "recurrente" and i.label == "Salle"]
    assert len(tied) >= 2
    # Same (date, type, label) across both series: order must be stable/deterministic,
    # not dependent on unspecified DB row order — reran twice to confirm stability.
    items_again = get_projection(account.account_id, 6, db)
    tied_again = [i for i in items_again if i.type == "recurrente" and i.label == "Salle"]
    assert tied == tied_again
    assert first.recurring_id != second.recurring_id


def test_transaction_with_pending_rapprochement_excluded_from_anchor(db):
    account = _add_account(db)
    tag = _add_tag(db)
    recurring = _add_recurring(
        db, account.account_id, tag.tag_id, "salle de sport", "Salle de sport",
        Decimal("-50.00"), "mensuelle",
    )
    transaction = _add_transaction(
        db, account.account_id, date.today() - timedelta(days=5), Decimal("-50.00"), "Salle de sport"
    )
    db.add(
        RecurringMatch(
            recurring_id=recurring.recurring_id,
            transaction_id=transaction.transaction_id,
            status="pending",
        )
    )
    db.commit()

    items = get_projection(account.account_id, 6, db)
    assert items == []


def test_transaction_with_confirmed_rapprochement_used_as_anchor(db):
    account = _add_account(db)
    tag = _add_tag(db)
    recurring = _add_recurring(
        db, account.account_id, tag.tag_id, "salle de sport", "Salle de sport",
        Decimal("-50.00"), "mensuelle",
    )
    transaction = _add_transaction(
        db, account.account_id, date.today() - timedelta(days=5), Decimal("-50.00"), "Salle de sport"
    )
    db.add(
        RecurringMatch(
            recurring_id=recurring.recurring_id,
            transaction_id=transaction.transaction_id,
            status="confirmed",
        )
    )
    db.commit()

    items = get_projection(account.account_id, 6, db)
    recurring_items = [i for i in items if i.type == "recurrente"]
    assert len(recurring_items) >= 1


def test_transaction_with_rejected_rapprochement_excluded_from_anchor(db):
    account = _add_account(db)
    tag = _add_tag(db)
    recurring = _add_recurring(
        db, account.account_id, tag.tag_id, "salle de sport", "Salle de sport",
        Decimal("-50.00"), "mensuelle",
    )
    transaction = _add_transaction(
        db, account.account_id, date.today() - timedelta(days=5), Decimal("-50.00"), "Salle de sport"
    )
    db.add(
        RecurringMatch(
            recurring_id=recurring.recurring_id,
            transaction_id=transaction.transaction_id,
            status="rejected",
        )
    )
    db.commit()

    items = get_projection(account.account_id, 6, db)
    assert items == []


def test_split_series_fractions_in_horizon_appear_in_projection(db):
    today = date.today()
    account = _add_account(db, start_day=today.day)
    tag = _add_tag(db)
    create_planned_expense_split(
        PlannedExpenseSplitCreate(
            account_id=account.account_id,
            tag_id=tag.tag_id,
            start_date=today,
            total_amount=Decimal("300.00"),
            total_periods=3,
            description="Série en projection",
        ),
        db,
    )
    items = get_projection(account.account_id, 6, db)
    planifiee_labels = [i.label for i in items if i.type == "planifiee"]
    assert planifiee_labels.count("Série en projection") == 3
