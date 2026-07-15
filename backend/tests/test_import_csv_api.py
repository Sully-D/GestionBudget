from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from app.transactions.model import Transaction
from main import app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _add_transaction_via_override(client, **kwargs):
    session = next(app.dependency_overrides[get_db]())
    try:
        transaction = Transaction(**kwargs)
        session.add(transaction)
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_import_csv_api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session_local() as session:
        session.add(Account(name="Personnel", is_common=False, start_day=1))
        session.commit()

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def account_id(client):
    accounts = client.get("/accounts").json()["data"]
    return accounts[0]["account_id"]


@pytest.fixture
def second_account_id(client):
    session = next(app.dependency_overrides[get_db]())
    try:
        account = Account(name="Commun", is_common=True, start_day=1)
        session.add(account)
        session.commit()
        session.refresh(account)
        return account.account_id
    finally:
        session.close()


@pytest.fixture
def sample_csv_bytes():
    return (FIXTURES_DIR / "sample.csv").read_bytes()


def _mapping_form_fields():
    return {
        "date_column": "Date_Operation",
        "montant_column": "Montant_EUR",
        "libelle_column": "Libelle_Complet",
        "tiers_column": "Beneficiaire",
    }


def test_post_import_csv_preview_returns_columns_and_preview(client, account_id, sample_csv_bytes):
    response = client.post(
        "/import/csv/preview",
        data={"account_id": account_id},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["columns"] == [
        "Date_Operation",
        "Montant_EUR",
        "Libelle_Complet",
        "Beneficiaire",
    ]
    assert len(data["preview_rows"]) == 3
    assert data["saved_mapping"] is None


def test_post_import_csv_imports_and_counts_skipped(client, account_id, sample_csv_bytes):
    response = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"imported_count": 3, "skipped_count": 1, "duplicate_count": 0}

    transactions = client.get(f"/transactions?account_id={account_id}").json()["data"]["transactions"]
    assert len(transactions) == 3


def test_post_import_csv_reimport_same_file_ignores_all_as_duplicates(client, account_id, sample_csv_bytes):
    first = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    second = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"] == {"imported_count": 0, "skipped_count": 1, "duplicate_count": 3}

    transactions = client.get(f"/transactions?account_id={account_id}").json()["data"]["transactions"]
    assert len(transactions) == 3


def test_post_import_csv_ambiguous_row_returns_pending_review(client, account_id):
    existing_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Carrefour\n"
    ).encode("utf-8")
    client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("first.csv", existing_csv, "text/csv")},
    )

    ambiguous_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR MARKET;Carrefour\n"
    ).encode("utf-8")
    response = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("second.csv", ambiguous_csv, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pending_review"] is True
    assert len(data["ambiguous_rows"]) == 1
    assert data["ambiguous_rows"][0]["row_index"] == 0
    assert data["ambiguous_rows"][0]["existing_label"] == "CARREFOUR"

    transactions = client.get(f"/transactions?account_id={account_id}").json()["data"]["transactions"]
    assert len(transactions) == 1


def test_post_import_csv_ambiguous_row_resolved_import_persists_it(client, account_id):
    existing_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR;Carrefour\n"
    ).encode("utf-8")
    client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("first.csv", existing_csv, "text/csv")},
    )

    ambiguous_csv = (
        "Date_Operation;Montant_EUR;Libelle_Complet;Beneficiaire\n"
        "01/07/2026;-10,00;CARREFOUR MARKET;Carrefour\n"
    ).encode("utf-8")
    response = client.post(
        "/import/csv",
        data={
            "account_id": account_id,
            **_mapping_form_fields(),
            "resolutions": '[{"row_index": 0, "decision": "import"}]',
        },
        files={"file": ("second.csv", ambiguous_csv, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"imported_count": 1, "skipped_count": 0, "duplicate_count": 0}

    transactions = client.get(f"/transactions?account_id={account_id}").json()["data"]["transactions"]
    assert len(transactions) == 2


def test_post_import_csv_invalid_resolutions_returns_400(client, account_id, sample_csv_bytes):
    response = client.post(
        "/import/csv",
        data={
            "account_id": account_id,
            **_mapping_form_fields(),
            "resolutions": "pas-du-json-valide",
        },
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 400


def test_post_import_csv_duplicate_row_index_in_resolutions_returns_400(
    client, account_id, sample_csv_bytes
):
    response = client.post(
        "/import/csv",
        data={
            "account_id": account_id,
            **_mapping_form_fields(),
            "resolutions": (
                '[{"row_index": 0, "decision": "import"}, '
                '{"row_index": 0, "decision": "ignore"}]'
            ),
        },
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 400


def test_post_import_csv_missing_required_field_returns_422(client, account_id, sample_csv_bytes):
    incomplete_fields = _mapping_form_fields()
    del incomplete_fields["libelle_column"]
    response = client.post(
        "/import/csv",
        data={"account_id": account_id, **incomplete_fields},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 422


def test_post_import_csv_wrong_extension_returns_400(client, account_id, sample_csv_bytes):
    response = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("sample.ofx", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 400


def test_post_import_csv_preview_wrong_extension_returns_400(client, account_id, sample_csv_bytes):
    response = client.post(
        "/import/csv/preview",
        data={"account_id": account_id},
        files={"file": ("sample.txt", sample_csv_bytes, "text/plain")},
    )
    assert response.status_code == 400


def test_post_import_csv_duplicate_mapped_column_returns_400(client, account_id, sample_csv_bytes):
    fields = _mapping_form_fields()
    fields["montant_column"] = fields["date_column"]
    response = client.post(
        "/import/csv",
        data={"account_id": account_id, **fields},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 400


def test_post_import_csv_matching_recurring_creates_pending_rapprochement(
    client, account_id, sample_csv_bytes
):
    _add_transaction_via_override(
        client,
        account_id=account_id,
        date=date(2026, 6, 1),
        amount=Decimal("-42.90"),
        label="CB CARREFOUR MARKET REIMS",
        payee="CARREFOUR",
    )
    client.post(
        "/recurring/confirm",
        json={
            "account_id": account_id,
            "signature": "carrefour",
            "label": "Carrefour Market",
            "amount": -42.90,
            "periodicity": "mensuelle",
        },
    )

    response = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200

    pending = client.get("/rapprochement/pending", params={"account_id": account_id})
    assert pending.status_code == 200
    data = pending.json()["data"]
    assert len(data) == 1
    assert data[0]["transaction_label"] == "CB CARREFOUR MARKET REIMS"


def test_post_import_csv_then_preview_returns_saved_mapping(client, account_id, sample_csv_bytes):
    import_response = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert import_response.status_code == 200

    preview_response = client.post(
        "/import/csv/preview",
        data={"account_id": account_id},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["data"]["saved_mapping"] == _mapping_form_fields()


def test_post_import_csv_preview_unknown_account_returns_404(client, sample_csv_bytes):
    response = client.post(
        "/import/csv/preview",
        data={"account_id": 999999},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 404


def test_post_import_csv_preview_different_account_has_no_saved_mapping(
    client, account_id, second_account_id, sample_csv_bytes
):
    import_response = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert import_response.status_code == 200

    preview_response = client.post(
        "/import/csv/preview",
        data={"account_id": second_account_id},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["data"]["saved_mapping"] is None
