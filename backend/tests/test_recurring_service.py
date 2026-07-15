from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.projections.model import RecurringTransaction
from app.projections.schema import (
    RecurringConfirmCreate,
    RecurringFromTransactionCreate,
    RecurringRejectCreate,
    RecurringTransactionUpdate,
)
from app.projections.service import (
    confirm_recurring,
    create_recurring_from_transaction,
    delete_recurring,
    detect_recurring_candidates,
    list_recurring,
    reject_recurring_candidate,
    update_recurring,
)
from app.tags.model import Rule, Tag
from app.transactions.model import Transaction


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_recurring_service.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
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


def _add_tag(db, name="Abonnements", parent_id=None, level=1) -> Tag:
    tag = Tag(name=name, parent_id=parent_id, level=level)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _add_transaction(db, account_id, txn_date, amount, label, payee=None) -> Transaction:
    transaction = Transaction(
        account_id=account_id, date=txn_date, amount=amount, label=label, payee=payee
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def _add_monthly_group(db, account, label="Salle de sport", payee=None, amount=Decimal("-50.00")):
    _add_transaction(db, account.account_id, date(2026, 1, 5), amount, label, payee)
    _add_transaction(db, account.account_id, date(2026, 2, 5), amount, label, payee)
    _add_transaction(db, account.account_id, date(2026, 3, 5), amount, label, payee)
    _add_transaction(db, account.account_id, date(2026, 4, 5), amount, label, payee)


def test_detect_regular_monthly_group_returns_one_candidate(db):
    account = _add_account(db)
    _add_monthly_group(db, account)
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    assert len(candidates) == 1
    assert candidates[0].periodicity == "mensuelle"
    assert candidates[0].occurrence_count == 4
    assert candidates[0].amount == Decimal("-50.00")


def test_detect_amount_outside_tolerance_excludes_group(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _add_transaction(db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport")
    _add_transaction(db, account.account_id, date(2026, 3, 5), Decimal("-60.00"), "Salle de sport")
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    assert candidates == []


def test_detect_irregular_intervals_excludes_group(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 1), Decimal("-50.00"), "Divers")
    _add_transaction(db, account.account_id, date(2026, 1, 11), Decimal("-50.00"), "Divers")
    _add_transaction(db, account.account_id, date(2026, 2, 25), Decimal("-50.00"), "Divers")
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    assert candidates == []


def test_detect_fewer_than_three_occurrences_excludes_group(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _add_transaction(db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport")
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    assert candidates == []


def test_detect_suggested_tag_present_when_rule_matches(db):
    account = _add_account(db)
    tag = _add_tag(db)
    db.add(Rule(condition_type="label_contains", condition_value="sport", tag_id=tag.tag_id, sort_order=1))
    db.commit()
    _add_monthly_group(db, account, label="Salle de sport")
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    assert candidates[0].suggested_tag_id == tag.tag_id
    assert candidates[0].suggested_tag_name == tag.name


def test_detect_suggested_tag_absent_when_no_rule_matches(db):
    account = _add_account(db)
    _add_monthly_group(db, account, label="Salle de sport")
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    assert candidates[0].suggested_tag_id is None
    assert candidates[0].suggested_tag_name is None


def test_detect_confirmed_signature_not_reproposed(db):
    account = _add_account(db)
    _add_monthly_group(db, account)
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    confirm_recurring(
        RecurringConfirmCreate(
            account_id=account.account_id,
            signature=candidates[0].signature,
            label=candidates[0].label,
            amount=candidates[0].amount,
            periodicity=candidates[0].periodicity,
        ),
        db,
    )
    assert detect_recurring_candidates(account.account_id, Decimal("10.00"), db) == []


def test_detect_rejected_signature_not_reproposed(db):
    account = _add_account(db)
    _add_monthly_group(db, account)
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    reject_recurring_candidate(
        RecurringRejectCreate(
            account_id=account.account_id,
            signature=candidates[0].signature,
            label=candidates[0].label,
            amount=candidates[0].amount,
            periodicity=candidates[0].periodicity,
        ),
        db,
    )
    assert detect_recurring_candidates(account.account_id, Decimal("10.00"), db) == []


def test_confirm_recurring_creates_confirmed_row_with_adjusted_values(db):
    account = _add_account(db)
    tag = _add_tag(db)
    recurring = confirm_recurring(
        RecurringConfirmCreate(
            account_id=account.account_id,
            signature="salle de sport",
            label="Salle de sport",
            amount=Decimal("-55.00"),
            periodicity="mensuelle",
            tag_id=tag.tag_id,
        ),
        db,
    )
    assert recurring.status == "confirmed"
    assert recurring.amount == Decimal("-55.00")
    assert recurring.tag_id == tag.tag_id


def test_reject_then_detect_no_longer_shows_candidate(db):
    account = _add_account(db)
    _add_monthly_group(db, account)
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    reject_recurring_candidate(
        RecurringRejectCreate(
            account_id=account.account_id,
            signature=candidates[0].signature,
            label=candidates[0].label,
            amount=candidates[0].amount,
            periodicity=candidates[0].periodicity,
        ),
        db,
    )
    assert detect_recurring_candidates(account.account_id, Decimal("10.00"), db) == []


def test_update_recurring_on_confirmed_row_updates_fields(db):
    account = _add_account(db)
    recurring = confirm_recurring(
        RecurringConfirmCreate(
            account_id=account.account_id,
            signature="salle de sport",
            label="Salle de sport",
            amount=Decimal("-50.00"),
            periodicity="mensuelle",
        ),
        db,
    )
    updated = update_recurring(
        recurring.recurring_id,
        RecurringTransactionUpdate(amount=Decimal("-60.00"), periodicity="trimestrielle"),
        db,
    )
    assert updated.amount == Decimal("-60.00")
    assert updated.periodicity == "trimestrielle"


def test_update_recurring_on_rejected_row_returns_422(db):
    account = _add_account(db)
    recurring = reject_recurring_candidate(
        RecurringRejectCreate(
            account_id=account.account_id,
            signature="salle de sport",
            label="Salle de sport",
            amount=Decimal("-50.00"),
            periodicity="mensuelle",
        ),
        db,
    )
    with pytest.raises(HTTPException) as exc_info:
        update_recurring(
            recurring.recurring_id,
            RecurringTransactionUpdate(amount=Decimal("-60.00"), periodicity="mensuelle"),
            db,
        )
    assert exc_info.value.status_code == 422


def test_delete_recurring_on_confirmed_removes_row(db):
    account = _add_account(db)
    recurring = confirm_recurring(
        RecurringConfirmCreate(
            account_id=account.account_id,
            signature="salle de sport",
            label="Salle de sport",
            amount=Decimal("-50.00"),
            periodicity="mensuelle",
        ),
        db,
    )
    delete_recurring(recurring.recurring_id, db)
    assert db.get(RecurringTransaction, recurring.recurring_id) is None


def test_delete_recurring_on_rejected_makes_signature_detectable_again(db):
    account = _add_account(db)
    _add_monthly_group(db, account)
    candidates = detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    rejected = reject_recurring_candidate(
        RecurringRejectCreate(
            account_id=account.account_id,
            signature=candidates[0].signature,
            label=candidates[0].label,
            amount=candidates[0].amount,
            periodicity=candidates[0].periodicity,
        ),
        db,
    )
    assert detect_recurring_candidates(account.account_id, Decimal("10.00"), db) == []
    delete_recurring(rejected.recurring_id, db)
    assert len(detect_recurring_candidates(account.account_id, Decimal("10.00"), db)) == 1


def test_detect_on_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    with pytest.raises(HTTPException) as exc_info:
        detect_recurring_candidates(account.account_id, Decimal("10.00"), db)
    assert exc_info.value.status_code == 422


def test_confirm_on_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    with pytest.raises(HTTPException) as exc_info:
        confirm_recurring(
            RecurringConfirmCreate(
                account_id=account.account_id,
                signature="salle de sport",
                label="Salle de sport",
                amount=Decimal("-50.00"),
                periodicity="mensuelle",
            ),
            db,
        )
    assert exc_info.value.status_code == 422


def test_detect_unknown_account_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        detect_recurring_candidates(999, Decimal("10.00"), db)
    assert exc_info.value.status_code == 404


def test_update_recurring_unknown_id_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        update_recurring(
            999, RecurringTransactionUpdate(amount=Decimal("-50.00"), periodicity="mensuelle"), db
        )
    assert exc_info.value.status_code == 404


def test_delete_recurring_unknown_id_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_recurring(999, db)
    assert exc_info.value.status_code == 404


def test_create_recurring_from_transaction_creates_confirmed_row(db):
    account = _add_account(db)
    tag = _add_tag(db)
    transaction = _add_transaction(
        db, account.account_id, date(2026, 5, 12), Decimal("-19.99"), "Abonnement Musique"
    )
    recurring = create_recurring_from_transaction(
        RecurringFromTransactionCreate(
            transaction_id=transaction.transaction_id,
            label="Abonnement Musique",
            amount=Decimal("-19.99"),
            periodicity="mensuelle",
            tag_id=tag.tag_id,
        ),
        db,
    )
    assert recurring.status == "confirmed"
    assert recurring.account_id == account.account_id
    assert recurring.amount == Decimal("-19.99")
    assert recurring.periodicity == "mensuelle"
    assert recurring.tag_id == tag.tag_id
    assert recurring.signature == "abonnement musique"


def test_create_recurring_from_transaction_positive_amount_returns_422(db):
    account = _add_account(db)
    transaction = _add_transaction(
        db, account.account_id, date(2026, 5, 12), Decimal("1500.00"), "Salaire"
    )
    with pytest.raises(HTTPException) as exc_info:
        create_recurring_from_transaction(
            RecurringFromTransactionCreate(
                transaction_id=transaction.transaction_id,
                label="Salaire",
                amount=Decimal("-1500.00"),
                periodicity="mensuelle",
            ),
            db,
        )
    assert exc_info.value.status_code == 422


def test_create_recurring_from_transaction_duplicate_signature_returns_422(db):
    account = _add_account(db)
    transaction = _add_transaction(
        db, account.account_id, date(2026, 5, 12), Decimal("-19.99"), "Abonnement Musique"
    )
    create_recurring_from_transaction(
        RecurringFromTransactionCreate(
            transaction_id=transaction.transaction_id,
            label="Abonnement Musique",
            amount=Decimal("-19.99"),
            periodicity="mensuelle",
        ),
        db,
    )
    other_transaction = _add_transaction(
        db, account.account_id, date(2026, 6, 12), Decimal("-19.99"), "Abonnement Musique"
    )
    with pytest.raises(HTTPException) as exc_info:
        create_recurring_from_transaction(
            RecurringFromTransactionCreate(
                transaction_id=other_transaction.transaction_id,
                label="Autre libellé saisi",
                amount=Decimal("-19.99"),
                periodicity="mensuelle",
            ),
            db,
        )
    assert exc_info.value.status_code == 422
    assert "Abonnement Musique" in exc_info.value.detail
    assert "Autre libellé saisi" not in exc_info.value.detail


def test_create_recurring_from_transaction_on_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    transaction = _add_transaction(
        db, account.account_id, date(2026, 5, 12), Decimal("-19.99"), "Abonnement Musique"
    )
    with pytest.raises(HTTPException) as exc_info:
        create_recurring_from_transaction(
            RecurringFromTransactionCreate(
                transaction_id=transaction.transaction_id,
                label="Abonnement Musique",
                amount=Decimal("-19.99"),
                periodicity="mensuelle",
            ),
            db,
        )
    assert exc_info.value.status_code == 422


def test_create_recurring_from_transaction_unknown_tag_returns_404(db):
    account = _add_account(db)
    transaction = _add_transaction(
        db, account.account_id, date(2026, 5, 12), Decimal("-19.99"), "Abonnement Musique"
    )
    with pytest.raises(HTTPException) as exc_info:
        create_recurring_from_transaction(
            RecurringFromTransactionCreate(
                transaction_id=transaction.transaction_id,
                label="Abonnement Musique",
                amount=Decimal("-19.99"),
                periodicity="mensuelle",
                tag_id=999,
            ),
            db,
        )
    assert exc_info.value.status_code == 404


def test_create_recurring_from_transaction_unknown_transaction_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        create_recurring_from_transaction(
            RecurringFromTransactionCreate(
                transaction_id=999,
                label="Abonnement Musique",
                amount=Decimal("-19.99"),
                periodicity="mensuelle",
            ),
            db,
        )
    assert exc_info.value.status_code == 404


def test_list_recurring_filters_by_status(db):
    account = _add_account(db)
    confirm_recurring(
        RecurringConfirmCreate(
            account_id=account.account_id,
            signature="a",
            label="A",
            amount=Decimal("-10.00"),
            periodicity="mensuelle",
        ),
        db,
    )
    reject_recurring_candidate(
        RecurringRejectCreate(
            account_id=account.account_id,
            signature="b",
            label="B",
            amount=Decimal("-10.00"),
            periodicity="mensuelle",
        ),
        db,
    )
    confirmed_only = list_recurring(account.account_id, "confirmed", db)
    all_rows = list_recurring(account.account_id, None, db)
    assert len(confirmed_only) == 1
    assert len(all_rows) == 2
