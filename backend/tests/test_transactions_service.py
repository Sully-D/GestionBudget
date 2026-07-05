from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.tags.model import Tag
from app.transactions.model import Transaction
from app.transactions.schema import TransactionCreate, TransactionUpdate
from app.transactions.service import (
    add_tag_to_transaction,
    create_transaction,
    delete_transaction,
    get_transaction,
    list_transactions,
    remove_tag_from_transaction,
    update_transaction,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_transactions_service.db"
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


def test_list_transactions_filters_by_current_period_and_sorts_desc(db, account):
    today = date.today()
    db.add_all(
        [
            Transaction(
                account_id=account.account_id,
                date=today,
                amount=Decimal("-10.00"),
                label="Plus récente",
            ),
            Transaction(
                account_id=account.account_id,
                date=today,
                amount=Decimal("-20.00"),
                label="Même jour, id plus petit",
            ),
        ]
    )
    db.commit()

    period_start, period_end, transactions = list_transactions(
        account.account_id, None, db
    )
    assert period_start <= today <= period_end
    assert len(transactions) == 2
    # tri date DESC puis transaction_id DESC (tie-break)
    assert transactions[0].transaction_id > transactions[1].transaction_id


def test_list_transactions_raises_404_when_account_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        list_transactions(999, None, db)
    assert exc_info.value.status_code == 404


def test_list_transactions_excludes_transactions_outside_period(db, account):
    old_date = date(2020, 1, 1)
    db.add(
        Transaction(
            account_id=account.account_id,
            date=old_date,
            amount=Decimal("-5.00"),
            label="Hors période",
        )
    )
    db.commit()

    _, _, transactions = list_transactions(account.account_id, None, db)
    assert transactions == []


def test_create_transaction_persists_and_returns_transaction(db, account):
    payload = TransactionCreate(
        account_id=account.account_id,
        date=date.today(),
        amount=Decimal("-42.90"),
        label="Carrefour",
        payee="Carrefour",
    )
    transaction = create_transaction(payload, db)
    assert transaction.transaction_id is not None
    assert transaction.amount == Decimal("-42.90")
    assert transaction.label == "Carrefour"
    assert transaction.payee == "Carrefour"


def test_create_transaction_raises_404_when_account_missing(db):
    payload = TransactionCreate(
        account_id=999,
        date=date.today(),
        amount=Decimal("-1.00"),
        label="Test",
    )
    with pytest.raises(HTTPException) as exc_info:
        create_transaction(payload, db)
    assert exc_info.value.status_code == 404


def test_get_transaction_returns_existing_transaction(db, account):
    transaction = Transaction(
        account_id=account.account_id,
        date=date.today(),
        amount=Decimal("-10.00"),
        label="Test",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    found = get_transaction(transaction.transaction_id, db)
    assert found.transaction_id == transaction.transaction_id


def test_get_transaction_raises_404_when_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        get_transaction(999, db)
    assert exc_info.value.status_code == 404


def test_update_transaction_updates_fields_and_preserves_account_id(db, account):
    transaction = Transaction(
        account_id=account.account_id,
        date=date(2026, 1, 1),
        amount=Decimal("-10.00"),
        label="Original",
        payee="Original Payee",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    payload = TransactionUpdate(
        date=date(2026, 2, 2),
        amount=Decimal("-20.00"),
        label="Modifié",
        payee="Nouveau Tiers",
    )
    updated = update_transaction(transaction.transaction_id, payload, db)

    assert updated.date == date(2026, 2, 2)
    assert updated.amount == Decimal("-20.00")
    assert updated.label == "Modifié"
    assert updated.payee == "Nouveau Tiers"
    # account_id est immuable : TransactionUpdate n'a pas de champ account_id,
    # donc il ne peut pas être modifié par cette fonction.
    assert updated.account_id == account.account_id


def test_update_transaction_raises_404_when_missing(db):
    payload = TransactionUpdate(
        date=date.today(), amount=Decimal("-1.00"), label="Test"
    )
    with pytest.raises(HTTPException) as exc_info:
        update_transaction(999, payload, db)
    assert exc_info.value.status_code == 404


def test_delete_transaction_removes_transaction(db, account):
    transaction = Transaction(
        account_id=account.account_id,
        date=date.today(),
        amount=Decimal("-10.00"),
        label="À supprimer",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    transaction_id = transaction.transaction_id

    delete_transaction(transaction_id, db)

    with pytest.raises(HTTPException) as exc_info:
        get_transaction(transaction_id, db)
    assert exc_info.value.status_code == 404


def test_delete_transaction_raises_404_when_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_transaction(999, db)
    assert exc_info.value.status_code == 404


@pytest.fixture
def transaction(db, account):
    transaction = Transaction(
        account_id=account.account_id,
        date=date.today(),
        amount=Decimal("-10.00"),
        label="Test",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@pytest.fixture
def tag(db):
    tag = Tag(name="Alimentation", parent_id=None, level=1)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@pytest.fixture
def other_tag(db):
    tag = Tag(name="Loisirs", parent_id=None, level=1)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def test_add_tag_to_transaction_associates_tag(db, transaction, tag):
    updated = add_tag_to_transaction(transaction.transaction_id, tag.tag_id, db)
    assert [t.tag_id for t in updated.tags] == [tag.tag_id]
    assert updated.tags[0].name == "Alimentation"


def test_add_tag_to_transaction_second_tag_keeps_both(db, transaction, tag, other_tag):
    add_tag_to_transaction(transaction.transaction_id, tag.tag_id, db)
    updated = add_tag_to_transaction(transaction.transaction_id, other_tag.tag_id, db)
    assert {t.tag_id for t in updated.tags} == {tag.tag_id, other_tag.tag_id}


def test_add_tag_to_transaction_twice_is_idempotent(db, transaction, tag):
    add_tag_to_transaction(transaction.transaction_id, tag.tag_id, db)
    updated = add_tag_to_transaction(transaction.transaction_id, tag.tag_id, db)
    assert [t.tag_id for t in updated.tags] == [tag.tag_id]


def test_add_tag_to_transaction_nonexistent_tag_raises_422(db, transaction):
    with pytest.raises(HTTPException) as exc_info:
        add_tag_to_transaction(transaction.transaction_id, 999, db)
    assert exc_info.value.status_code == 422


def test_add_tag_to_transaction_nonexistent_transaction_raises_404(db, tag):
    with pytest.raises(HTTPException) as exc_info:
        add_tag_to_transaction(999, tag.tag_id, db)
    assert exc_info.value.status_code == 404


def test_remove_tag_from_transaction_removes_only_targeted_tag(
    db, transaction, tag, other_tag
):
    add_tag_to_transaction(transaction.transaction_id, tag.tag_id, db)
    add_tag_to_transaction(transaction.transaction_id, other_tag.tag_id, db)

    remove_tag_from_transaction(transaction.transaction_id, tag.tag_id, db)

    remaining = get_transaction(transaction.transaction_id, db)
    assert [t.tag_id for t in remaining.tags] == [other_tag.tag_id]


def test_remove_tag_from_transaction_absent_association_is_noop(db, transaction, tag):
    remove_tag_from_transaction(transaction.transaction_id, tag.tag_id, db)
    remaining = get_transaction(transaction.transaction_id, db)
    assert remaining.tags == []


def test_remove_tag_from_transaction_nonexistent_transaction_raises_404(db, tag):
    with pytest.raises(HTTPException) as exc_info:
        remove_tag_from_transaction(999, tag.tag_id, db)
    assert exc_info.value.status_code == 404


def test_list_transactions_and_get_transaction_untagged_return_empty_tags(
    db, account, transaction
):
    _, _, transactions = list_transactions(account.account_id, None, db)
    assert transactions[0].tags == []

    fetched = get_transaction(transaction.transaction_id, db)
    assert fetched.tags == []


def test_list_transactions_does_not_leak_tags_across_transactions(
    db, account, transaction, tag, other_tag
):
    second = Transaction(
        account_id=account.account_id,
        date=date.today(),
        amount=Decimal("-5.00"),
        label="Autre transaction",
    )
    db.add(second)
    db.commit()
    db.refresh(second)

    add_tag_to_transaction(transaction.transaction_id, tag.tag_id, db)
    add_tag_to_transaction(second.transaction_id, other_tag.tag_id, db)

    _, _, transactions = list_transactions(account.account_id, None, db)
    tags_by_transaction = {t.transaction_id: {tag.tag_id for tag in t.tags} for t in transactions}

    assert tags_by_transaction[transaction.transaction_id] == {tag.tag_id}
    assert tags_by_transaction[second.transaction_id] == {other_tag.tag_id}


def test_delete_transaction_with_tags_removes_associations(db, transaction, tag):
    add_tag_to_transaction(transaction.transaction_id, tag.tag_id, db)

    delete_transaction(transaction.transaction_id, db)

    with pytest.raises(HTTPException) as exc_info:
        get_transaction(transaction.transaction_id, db)
    assert exc_info.value.status_code == 404
