from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.import_pipeline.pipeline import import_ofx
from app.tags.model import Rule, Tag
from app.transactions.model import Transaction

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_import_pipeline.db"
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


@pytest.fixture
def sample_ofx_bytes():
    return (FIXTURES_DIR / "sample.ofx").read_bytes()


@pytest.fixture
def duplicate_fitid_ofx_bytes():
    return (FIXTURES_DIR / "duplicate_fitid.ofx").read_bytes()


def test_import_on_empty_account_inserts_two_and_no_duplicates(db, account, sample_ofx_bytes):
    imported_count, duplicate_count, transaction_ids = import_ofx(
        account.account_id, sample_ofx_bytes, db
    )
    assert imported_count == 2
    assert duplicate_count == 0
    assert len(transaction_ids) == 2
    assert db.query(Transaction).count() == 2


def test_reimport_same_file_same_account_inserts_nothing_and_keeps_data(
    db, account, sample_ofx_bytes
):
    import_ofx(account.account_id, sample_ofx_bytes, db)
    ids_before = {t.transaction_id for t in db.query(Transaction).all()}

    imported_count, duplicate_count, transaction_ids = import_ofx(
        account.account_id, sample_ofx_bytes, db
    )
    assert imported_count == 0
    assert duplicate_count == 2
    assert transaction_ids == []

    ids_after = {t.transaction_id for t in db.query(Transaction).all()}
    assert ids_after == ids_before


def test_import_nonexistent_account_raises_404(db, sample_ofx_bytes):
    with pytest.raises(HTTPException) as exc_info:
        import_ofx(999, sample_ofx_bytes, db)
    assert exc_info.value.status_code == 404


def test_import_unreadable_file_raises_400(db, account):
    with pytest.raises(HTTPException) as exc_info:
        import_ofx(account.account_id, b"not an ofx file", db)
    assert exc_info.value.status_code == 400
    assert db.query(Transaction).count() == 0


def test_import_rolls_back_on_persist_error(db, account, sample_ofx_bytes, monkeypatch):
    rollback_calls = []
    original_rollback = db.rollback

    def spy_rollback():
        rollback_calls.append(True)
        original_rollback()

    def boom():
        raise SQLAlchemyError("simulated failure")

    monkeypatch.setattr(db, "commit", boom)
    monkeypatch.setattr(db, "rollback", spy_rollback)

    with pytest.raises(HTTPException) as exc_info:
        import_ofx(account.account_id, sample_ofx_bytes, db)

    assert exc_info.value.status_code == 400
    assert rollback_calls == [True]
    assert db.query(Transaction).count() == 0


def test_import_deduplicates_two_rows_sharing_one_fitid_in_same_file(
    db, account, duplicate_fitid_ofx_bytes
):
    imported_count, duplicate_count, transaction_ids = import_ofx(
        account.account_id, duplicate_fitid_ofx_bytes, db
    )
    assert imported_count == 1
    assert duplicate_count == 1
    assert len(transaction_ids) == 1
    assert db.query(Transaction).count() == 1


def test_import_applies_matching_payee_exact_rule(db, account, sample_ofx_bytes):
    tag = Tag(name="Alimentation", parent_id=None, level=1)
    db.add(tag)
    db.commit()
    db.refresh(tag)

    rule = Rule(
        condition_type="payee_exact",
        condition_value="CARREFOUR MARKET",
        tag_id=tag.tag_id,
        sort_order=1,
    )
    db.add(rule)
    db.commit()

    import_ofx(account.account_id, sample_ofx_bytes, db)

    transaction = (
        db.query(Transaction).filter(Transaction.fitid == "2026061500001").one()
    )
    assert [t.tag_id for t in transaction.tags] == [tag.tag_id]


def test_import_applies_only_first_matching_rule_when_several_match(
    db, account, sample_ofx_bytes
):
    # AD-6 : au plus 1 Tag automatique par Transaction, premier match gagne —
    # vérifié ici de bout en bout (import réel), pas seulement au niveau du
    # dispatcher isolé.
    tag_first = Tag(name="Alimentation", parent_id=None, level=1)
    tag_second = Tag(name="Autre", parent_id=None, level=1)
    db.add_all([tag_first, tag_second])
    db.commit()
    db.refresh(tag_first)
    db.refresh(tag_second)

    rule_first = Rule(
        condition_type="payee_exact",
        condition_value="CARREFOUR MARKET",
        tag_id=tag_first.tag_id,
        sort_order=1,
    )
    rule_second = Rule(
        condition_type="label_contains",
        condition_value="CARREFOUR",
        tag_id=tag_second.tag_id,
        sort_order=2,
    )
    db.add_all([rule_first, rule_second])
    db.commit()

    import_ofx(account.account_id, sample_ofx_bytes, db)

    transaction = (
        db.query(Transaction).filter(Transaction.fitid == "2026061500001").one()
    )
    assert [t.tag_id for t in transaction.tags] == [tag_first.tag_id]
