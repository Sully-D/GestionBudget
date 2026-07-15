from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.import_pipeline.csv_parser import ColumnMapping
from app.import_pipeline.model import CsvColumnMapping
from app.import_pipeline.pipeline import import_csv, preview_csv
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
    imported_count, skipped_count, transaction_ids = import_csv(
        account.account_id, sample_csv_bytes, default_mapping, db
    )
    assert imported_count == 3
    assert skipped_count == 1
    assert len(transaction_ids) == 3
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
    imported_count_1, _, _ = import_csv(account.account_id, sample_csv_bytes, default_mapping, db)
    imported_count_2, _, _ = import_csv(account.account_id, sample_csv_bytes, default_mapping, db)
    assert imported_count_1 == 3
    assert imported_count_2 == 3
    assert db.query(Transaction).count() == 6


def test_import_csv_first_import_creates_csv_column_mapping(db, account, sample_csv_bytes, default_mapping):
    import_csv(account.account_id, sample_csv_bytes, default_mapping, db)

    saved = db.query(CsvColumnMapping).filter(CsvColumnMapping.account_id == account.account_id).one()
    assert saved.date_column == default_mapping.date_column
    assert saved.montant_column == default_mapping.montant_column
    assert saved.libelle_column == default_mapping.libelle_column
    assert saved.tiers_column == default_mapping.tiers_column


def test_import_csv_reimport_with_different_mapping_updates_existing_row_without_duplicate(
    db, account, sample_csv_bytes, default_mapping
):
    import_csv(account.account_id, sample_csv_bytes, default_mapping, db)

    updated_mapping = ColumnMapping(
        date_column=default_mapping.date_column,
        montant_column=default_mapping.montant_column,
        libelle_column=default_mapping.libelle_column,
        tiers_column=None,
    )
    import_csv(account.account_id, sample_csv_bytes, updated_mapping, db)

    rows = db.query(CsvColumnMapping).filter(CsvColumnMapping.account_id == account.account_id).all()
    assert len(rows) == 1
    assert rows[0].tiers_column is None


def test_preview_csv_unknown_account_raises_404(db, sample_csv_bytes):
    with pytest.raises(HTTPException) as exc_info:
        preview_csv(sample_csv_bytes, 999, db)
    assert exc_info.value.status_code == 404


def test_import_csv_all_rows_skipped_does_not_save_mapping(db, account, sample_csv_bytes):
    # date_column pointe vers une colonne texte (Beneficiaire) : aucune valeur
    # n'est parsable comme date, donc toutes les lignes sont ignorées.
    all_skip_mapping = ColumnMapping(
        date_column="Beneficiaire",
        montant_column="Montant_EUR",
        libelle_column="Libelle_Complet",
        tiers_column=None,
    )
    imported_count, skipped_count, transaction_ids = import_csv(
        account.account_id, sample_csv_bytes, all_skip_mapping, db
    )
    assert imported_count == 0
    assert skipped_count == 4
    assert transaction_ids == []
    assert db.query(CsvColumnMapping).filter(CsvColumnMapping.account_id == account.account_id).count() == 0


def test_import_csv_two_accounts_same_headers_have_distinct_mapping_rows(db, sample_csv_bytes, default_mapping):
    account_a = Account(name="Compte A", is_common=False, start_day=1)
    account_b = Account(name="Compte B", is_common=False, start_day=1)
    db.add_all([account_a, account_b])
    db.commit()
    db.refresh(account_a)
    db.refresh(account_b)

    import_csv(account_a.account_id, sample_csv_bytes, default_mapping, db)
    import_csv(account_b.account_id, sample_csv_bytes, default_mapping, db)

    rows = db.query(CsvColumnMapping).all()
    assert len(rows) == 2
    assert {row.account_id for row in rows} == {account_a.account_id, account_b.account_id}
