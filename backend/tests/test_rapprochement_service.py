from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.projections.model import RecurringMatch, RecurringTransaction
from app.projections.rapprochement import (
    confirm_rapprochement,
    list_pending_rapprochements,
    propose_if_match,
    reject_rapprochement,
)
from app.projections.schema import RecurringConfirmCreate, RecurringRejectCreate
from app.projections.service import confirm_recurring, reject_recurring_candidate
from app.transactions.model import Transaction


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_rapprochement_service.db"
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


def _add_transaction(db, account_id, txn_date, amount, label, payee=None) -> Transaction:
    transaction = Transaction(
        account_id=account_id, date=txn_date, amount=amount, label=label, payee=payee
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def _confirm_recurring(
    db, account_id, signature="salle de sport", label="Salle de sport",
    amount=Decimal("-50.00"), periodicity="mensuelle",
) -> RecurringTransaction:
    return confirm_recurring(
        RecurringConfirmCreate(
            account_id=account_id,
            signature=signature,
            label=label,
            amount=amount,
            periodicity=periodicity,
        ),
        db,
    )


def test_propose_if_match_within_tolerance_creates_pending_match(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )

    match = propose_if_match(new_txn.transaction_id, db)

    assert match is not None
    assert match.status == "pending"
    assert match.transaction_id == new_txn.transaction_id
    persisted = db.get(RecurringMatch, match.match_id)
    assert persisted is not None


def test_propose_if_match_amount_outside_tolerance_returns_none(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-52.01"), "Salle de sport"
    )

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_propose_if_match_date_outside_tolerance_returns_none(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 9), Decimal("-50.00"), "Salle de sport"
    )

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_propose_if_match_no_matching_signature_returns_none(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Autre Libellé"
    )

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_propose_if_match_rejected_recurring_never_candidate(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    reject_recurring_candidate(
        RecurringRejectCreate(
            account_id=account.account_id,
            signature="salle de sport",
            label="Salle de sport",
            amount=Decimal("-50.00"),
            periodicity="mensuelle",
        ),
        db,
    )
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_propose_if_match_positive_transaction_returns_none_without_exception(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("50.00"), "Salle de sport"
    )

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_propose_if_match_commit_failure_returns_none_without_exception(db, monkeypatch):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )

    def _raise_on_commit():
        raise Exception("boom")

    monkeypatch.setattr(db, "commit", _raise_on_commit)

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_propose_if_match_common_account_returns_none_without_exception(db):
    account = _add_account(db, is_common=True, name="Commun")
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_propose_if_match_idempotent_when_match_already_exists(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )
    first_match = propose_if_match(new_txn.transaction_id, db)
    assert first_match is not None

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_propose_if_match_two_candidates_same_signature_only_first_matched(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    first_recurring = _confirm_recurring(db, account.account_id)
    second_recurring = _confirm_recurring(db, account.account_id)
    assert first_recurring.recurring_id < second_recurring.recurring_id

    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )
    match = propose_if_match(new_txn.transaction_id, db)

    assert match is not None
    assert match.recurring_id == first_recurring.recurring_id


def test_propose_if_match_recurring_without_anchor_returns_none(db):
    account = _add_account(db)
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )

    assert propose_if_match(new_txn.transaction_id, db) is None


def test_confirm_rapprochement_transitions_pending_to_confirmed(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )
    match = propose_if_match(new_txn.transaction_id, db)

    confirmed = confirm_rapprochement(match.match_id, db)
    assert confirmed.status == "confirmed"


def test_confirm_rapprochement_already_confirmed_returns_422(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )
    match = propose_if_match(new_txn.transaction_id, db)
    confirm_rapprochement(match.match_id, db)

    with pytest.raises(HTTPException) as exc_info:
        confirm_rapprochement(match.match_id, db)
    assert exc_info.value.status_code == 422


def test_confirm_rapprochement_unknown_id_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        confirm_rapprochement(999, db)
    assert exc_info.value.status_code == 404


def test_reject_rapprochement_marks_status_rejected(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )
    match = propose_if_match(new_txn.transaction_id, db)

    reject_rapprochement(match.match_id, db)

    persisted = db.get(RecurringMatch, match.match_id)
    assert persisted is not None
    assert persisted.status == "rejected"
    assert list_pending_rapprochements(account.account_id, db) == []


def test_reject_rapprochement_confirmed_returns_422(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    new_txn = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )
    match = propose_if_match(new_txn.transaction_id, db)
    confirm_rapprochement(match.match_id, db)

    with pytest.raises(HTTPException) as exc_info:
        reject_rapprochement(match.match_id, db)
    assert exc_info.value.status_code == 422


def test_reject_rapprochement_unknown_id_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        reject_rapprochement(999, db)
    assert exc_info.value.status_code == 404


def test_list_pending_rapprochements_only_pending_for_account_sorted(db):
    account = _add_account(db)
    _add_transaction(db, account.account_id, date(2026, 1, 5), Decimal("-50.00"), "Salle de sport")
    _confirm_recurring(db, account.account_id)
    txn_a = _add_transaction(
        db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Salle de sport"
    )
    match_a = propose_if_match(txn_a.transaction_id, db)
    confirm_rapprochement(match_a.match_id, db)

    _add_transaction(db, account.account_id, date(2026, 2, 5), Decimal("-50.00"), "Autre Libellé")
    _confirm_recurring(db, account.account_id, signature="autre libellé", label="Autre Libellé")
    txn_b = _add_transaction(
        db, account.account_id, date(2026, 3, 5), Decimal("-50.00"), "Autre Libellé"
    )
    match_b = propose_if_match(txn_b.transaction_id, db)

    pending = list_pending_rapprochements(account.account_id, db)
    assert [m.match_id for m in pending] == [match_b.match_id]
