from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from main import app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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
def sample_csv_bytes():
    return (FIXTURES_DIR / "sample.csv").read_bytes()


def _mapping_form_fields():
    return {
        "date_column": "Date_Operation",
        "montant_column": "Montant_EUR",
        "libelle_column": "Libelle_Complet",
        "tiers_column": "Beneficiaire",
    }


def test_post_import_csv_preview_returns_columns_and_preview(client, sample_csv_bytes):
    response = client.post(
        "/import/csv/preview",
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


def test_post_import_csv_imports_and_counts_skipped(client, account_id, sample_csv_bytes):
    response = client.post(
        "/import/csv",
        data={"account_id": account_id, **_mapping_form_fields()},
        files={"file": ("sample.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"imported_count": 3, "skipped_count": 1}

    transactions = client.get(f"/transactions?account_id={account_id}").json()["data"]["transactions"]
    assert len(transactions) == 3


def test_post_import_csv_reimport_creates_duplicates(client, account_id, sample_csv_bytes):
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
    assert second.json()["data"] == {"imported_count": 3, "skipped_count": 1}

    transactions = client.get(f"/transactions?account_id={account_id}").json()["data"]["transactions"]
    assert len(transactions) == 6


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


def test_post_import_csv_preview_wrong_extension_returns_400(client, sample_csv_bytes):
    response = client.post(
        "/import/csv/preview",
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
