from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base
from app.import_pipeline.csv_parser import ColumnMapping
from app.import_pipeline.model import CsvColumnMapping
from app.import_pipeline.pipeline import CsvImportPending, CsvImportPersisted, import_csv, preview_csv
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
    outcome = import_csv(account.account_id, sample_csv_bytes, default_mapping, db)
    assert outcome.imported_count == 3
    assert outcome.skipped_count == 1
    assert outcome.duplicate_count == 0
    assert len(outcome.transaction_ids) == 3
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


def test_import_csv_reimport_same_file_ignores_all_as_duplicates(db, account, sample_csv_bytes, default_mapping):
    first = import_csv(account.account_id, sample_csv_bytes, default_mapping, db)
    second = import_csv(account.account_id, sample_csv_bytes, default_mapping, db)
    assert first.imported_count == 3
    assert second.imported_count == 0
    assert second.duplicate_count == 3
    assert db.query(Transaction).count() == 3


def test_import_csv_first_import_creates_csv_column_mapping(db, account, sample_csv_bytes, default_mapping):
    import_csv(account.account_id, sample_csv_bytes, default_mapping, db)

    saved = db.query(CsvColumnMapping).filter(CsvColumnMapping.account_id == account.account_id).one()
    assert saved.date_column == default_mapping.date_column
    assert saved.montant_column == default_mapping.montant_column
    assert saved.libelle_column == default_mapping.libelle_column
    assert saved.tiers_column == default_mapping.tiers_column


def test_import_csv_remap_on_new_data_updates_existing_mapping_row(db, account, default_mapping):
    # Deux petits fichiers autonomes (mêmes en-têtes, données distinctes) pour isoler
    # le remappage de la déduplication : le second import ne doit entrer en collision
    # avec rien du premier, afin de vérifier que le mappage mémorisé est bien mis à
    # jour dès qu'au moins une transaction est réellement persistée.
    csv_bytes_1 = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;Achat A;Fournisseur A\n"
    ).encode("utf-8")
    csv_bytes_2 = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "02/07/2026;-20,00;Achat B;Fournisseur B\n"
    ).encode("utf-8")

    import_csv(account.account_id, csv_bytes_1, default_mapping, db)

    updated_mapping = ColumnMapping(
        date_column=default_mapping.date_column,
        montant_column=default_mapping.montant_column,
        libelle_column=default_mapping.libelle_column,
        tiers_column=None,
    )
    outcome = import_csv(account.account_id, csv_bytes_2, updated_mapping, db)
    assert outcome.imported_count == 1

    rows = db.query(CsvColumnMapping).filter(CsvColumnMapping.account_id == account.account_id).all()
    assert len(rows) == 1
    assert rows[0].tiers_column is None


def test_import_csv_exact_duplicate_across_two_imports_is_ignored(db, account, default_mapping):
    csv_bytes = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;Achat A;Fournisseur A\n"
    ).encode("utf-8")

    import_csv(account.account_id, csv_bytes, default_mapping, db)
    outcome = import_csv(account.account_id, csv_bytes, default_mapping, db)

    assert outcome.imported_count == 0
    assert outcome.duplicate_count == 1
    assert db.query(Transaction).count() == 1


def test_import_csv_duplicate_within_same_batch_is_ignored(db, account, default_mapping):
    csv_bytes = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;Achat A;Fournisseur A\n"
        "01/07/2026;-10,00;Achat A;Fournisseur A\n"
    ).encode("utf-8")

    outcome = import_csv(account.account_id, csv_bytes, default_mapping, db)

    assert outcome.imported_count == 1
    assert outcome.duplicate_count == 1
    assert db.query(Transaction).count() == 1


def test_import_csv_ambiguous_row_blocks_import_without_resolutions(db, account, default_mapping):
    existing_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Carrefour\n"
    ).encode("utf-8")
    import_csv(account.account_id, existing_csv, default_mapping, db)

    ambiguous_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR MARKET;Carrefour\n"
    ).encode("utf-8")
    outcome = import_csv(account.account_id, ambiguous_csv, default_mapping, db)

    assert isinstance(outcome, CsvImportPending)
    assert len(outcome.ambiguous_rows) == 1
    assert outcome.ambiguous_rows[0].row_index == 0
    assert outcome.ambiguous_rows[0].existing_label == "CARREFOUR"
    # Rien n'est écrit tant que la ligne ambiguë n'est pas résolue.
    assert db.query(Transaction).count() == 1
    assert db.query(CsvColumnMapping).count() == 1  # inchangé depuis le premier import


def test_import_csv_ambiguous_row_resolved_import_is_persisted(db, account, default_mapping):
    existing_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Carrefour\n"
    ).encode("utf-8")
    import_csv(account.account_id, existing_csv, default_mapping, db)

    ambiguous_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR MARKET;Carrefour\n"
    ).encode("utf-8")
    outcome = import_csv(
        account.account_id, ambiguous_csv, default_mapping, db, resolutions={0: "import"}
    )

    assert isinstance(outcome, CsvImportPersisted)
    assert outcome.imported_count == 1
    assert db.query(Transaction).count() == 2


def test_import_csv_ambiguous_row_resolved_ignore_is_not_persisted(db, account, default_mapping):
    existing_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Carrefour\n"
    ).encode("utf-8")
    import_csv(account.account_id, existing_csv, default_mapping, db)

    ambiguous_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR MARKET;Carrefour\n"
    ).encode("utf-8")
    outcome = import_csv(
        account.account_id, ambiguous_csv, default_mapping, db, resolutions={0: "ignore"}
    )

    assert isinstance(outcome, CsvImportPersisted)
    assert outcome.imported_count == 0
    assert outcome.duplicate_count == 1
    assert db.query(Transaction).count() == 1


def test_import_csv_two_identical_ambiguous_rows_both_resolved_import_are_both_persisted(
    db, account, default_mapping
):
    existing_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Carrefour\n"
    ).encode("utf-8")
    import_csv(account.account_id, existing_csv, default_mapping, db)

    # Deux lignes ambiguës STRICTEMENT IDENTIQUES entre elles (même
    # date+montant+libellé+tiers), toutes deux différentes de la transaction
    # existante. Régression : la résolution "import" de la première ne doit
    # jamais faire passer la seconde pour un doublon certain de la première
    # (cf. dedup.py -- la résolution explicite est vérifiée avant is_exact_match).
    ambiguous_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR MARKET;Carrefour\n"
        "01/07/2026;-10,00;CARREFOUR MARKET;Carrefour\n"
    ).encode("utf-8")
    first_pass = import_csv(account.account_id, ambiguous_csv, default_mapping, db)
    assert isinstance(first_pass, CsvImportPending)
    assert len(first_pass.ambiguous_rows) == 2

    outcome = import_csv(
        account.account_id,
        ambiguous_csv,
        default_mapping,
        db,
        resolutions={0: "import", 1: "import"},
    )

    assert isinstance(outcome, CsvImportPersisted)
    assert outcome.imported_count == 2
    assert outcome.duplicate_count == 0
    assert (
        db.query(Transaction).filter(Transaction.label == "CARREFOUR MARKET").count() == 2
    )


def test_import_csv_mixed_batch_blocks_entirely_until_ambiguous_resolved(db, account, default_mapping):
    existing_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Carrefour\n"
    ).encode("utf-8")
    import_csv(account.account_id, existing_csv, default_mapping, db)

    # Mélange dans un même fichier : doublon exact (auto-ignoré), ligne ambiguë
    # (bloquante), ligne neuve. La ligne neuve ne doit PAS être persistée seule
    # tant que la ligne ambiguë n'est pas tranchée -- pas de persistance partielle.
    mixed_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Carrefour\n"
        "01/07/2026;-10,00;CARREFOUR MARKET;Carrefour\n"
        "02/07/2026;-5,00;BOULANGERIE;Boulangerie\n"
    ).encode("utf-8")
    outcome = import_csv(account.account_id, mixed_csv, default_mapping, db)

    assert isinstance(outcome, CsvImportPending)
    assert len(outcome.ambiguous_rows) == 1
    assert outcome.ambiguous_rows[0].row_index == 1
    assert db.query(Transaction).count() == 1

    resolved = import_csv(
        account.account_id, mixed_csv, default_mapping, db, resolutions={1: "ignore"}
    )
    assert isinstance(resolved, CsvImportPersisted)
    assert resolved.imported_count == 1
    assert resolved.duplicate_count == 2
    assert db.query(Transaction).count() == 2


def test_import_csv_unmapped_tiers_excludes_payee_from_matching(db, account):
    mapping_no_tiers = ColumnMapping(
        date_column="Date_Operation",
        montant_column="Montant_EUR",
        libelle_column="Libelle_Complet",
        tiers_column=None,
    )
    existing_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Fournisseur A\n"
    ).encode("utf-8")
    import_csv(account.account_id, existing_csv, mapping_no_tiers, db)

    # Même date/montant/libellé, tiers différent -- mais tiers non mappé cette
    # fois : doit être un doublon certain (payee exclu du calcul), pas ambigu.
    same_csv_different_payee = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Fournisseur B\n"
    ).encode("utf-8")
    outcome = import_csv(account.account_id, same_csv_different_payee, mapping_no_tiers, db)

    assert isinstance(outcome, CsvImportPersisted)
    assert outcome.imported_count == 0
    assert outcome.duplicate_count == 1


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
    outcome = import_csv(account.account_id, sample_csv_bytes, all_skip_mapping, db)
    assert outcome.imported_count == 0
    assert outcome.skipped_count == 4
    assert outcome.transaction_ids == []
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
