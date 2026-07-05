from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.import_pipeline.csv_parser import ColumnMapping
from app.import_pipeline.pipeline import import_csv
from app.tags.model import Rule, Tag
from app.transactions.model import Transaction

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_import_csv_pipeline.db"
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
def sample_csv_bytes():
    return (FIXTURES_DIR / "sample.csv").read_bytes()


@pytest.fixture
def default_mapping():
    return ColumnMapping(
        date_column="Date_Operation",
        montant_column="Montant_EUR",
        libelle_column="Libelle_Complet",
        tiers_column="Beneficiaire",
    )


def test_import_csv_inserts_valid_rows_and_counts_skipped(db, account, sample_csv_bytes, default_mapping):
    imported_count, skipped_count = import_csv(account.account_id, sample_csv_bytes, default_mapping, db)
    assert imported_count == 3
    assert skipped_count == 1
    assert db.query(Transaction).count() == 3


def test_import_csv_unknown_account_raises_404(db, sample_csv_bytes, default_mapping):
    with pytest.raises(HTTPException) as exc_info:
        import_csv(999, sample_csv_bytes, default_mapping, db)
    assert exc_info.value.status_code == 404


def test_import_csv_unknown_mapped_column_raises_400(db, account, sample_csv_bytes):
    bad_mapping = ColumnMapping(
        date_column="Colonne_Inexistante",
        montant_column="Montant_EUR",
        libelle_column="Libelle_Complet",
        tiers_column=None,
    )
    with pytest.raises(HTTPException) as exc_info:
        import_csv(account.account_id, sample_csv_bytes, bad_mapping, db)
    assert exc_info.value.status_code == 400


def test_import_csv_applies_matching_rule(db, account, sample_csv_bytes, default_mapping):
    tag = Tag(name="Alimentation", level=1)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    rule = Rule(condition_type="payee_exact", condition_value="CARREFOUR", tag_id=tag.tag_id, sort_order=1)
    db.add(rule)
    db.commit()

    import_csv(account.account_id, sample_csv_bytes, default_mapping, db)

    transaction = (
        db.query(Transaction)
        .filter(Transaction.payee == "CARREFOUR")
        .one()
    )
    assert tag in transaction.tags


def test_import_csv_reimport_creates_duplicates_without_error(db, account, sample_csv_bytes, default_mapping):
    imported_count_1, _ = import_csv(account.account_id, sample_csv_bytes, default_mapping, db)
    imported_count_2, _ = import_csv(account.account_id, sample_csv_bytes, default_mapping, db)
    assert imported_count_1 == 3
    assert imported_count_2 == 3
    assert db.query(Transaction).count() == 6
