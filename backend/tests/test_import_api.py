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
    db_path = tmp_path / "test_import_api.db"
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
def sample_ofx_bytes():
    return (FIXTURES_DIR / "sample.ofx").read_bytes()


def _post_import(client, account_id, content, filename="sample.ofx"):
    return client.post(
        "/import/ofx",
        data={"account_id": str(account_id)},
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_post_import_ofx_valid_imports_and_lists_transactions_sorted_desc(
    client, account_id, sample_ofx_bytes
):
    response = _post_import(client, account_id, sample_ofx_bytes)
    assert response.status_code == 200
    assert response.json()["data"] == {"imported_count": 2, "duplicate_count": 0}

    # Le fixture sample.ofx date ses transactions en juin 2026 : reference_date
    # cible explicitement cette Période pour que GET /transactions les inclue
    # (filtrage par Période courante, indépendant de la date du jour du test).
    transactions_response = client.get(
        f"/transactions?account_id={account_id}&reference_date=2026-06-15"
    )
    transactions = transactions_response.json()["data"]["transactions"]
    assert len(transactions) == 2
    dates = [t["date"] for t in transactions]
    assert dates == sorted(dates, reverse=True)


def test_post_import_ofx_reimport_same_file_yields_zero_imported(
    client, account_id, sample_ofx_bytes
):
    _post_import(client, account_id, sample_ofx_bytes)
    response = _post_import(client, account_id, sample_ofx_bytes)
    assert response.status_code == 200
    assert response.json()["data"] == {"imported_count": 0, "duplicate_count": 2}


def test_post_import_ofx_nonexistent_account_returns_404(client, sample_ofx_bytes):
    response = _post_import(client, 999, sample_ofx_bytes)
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_post_import_ofx_non_ofx_file_returns_400(client, account_id):
    response = _post_import(client, account_id, b"not an ofx file", filename="notes.txt")
    assert response.status_code == 400
    assert response.json()["detail"] == "Fichier OFX illisible ou Compte incorrect."


def test_post_import_ofx_applies_matching_rule_tag(client, account_id, sample_ofx_bytes):
    tag_id = client.post("/tags", json={"name": "Alimentation"}).json()["data"]["tag_id"]
    client.post(
        "/rules",
        json={
            "condition_type": "payee_exact",
            "condition_value": "CARREFOUR MARKET",
            "tag_id": tag_id,
        },
    )

    _post_import(client, account_id, sample_ofx_bytes)

    transactions = client.get(
        f"/transactions?account_id={account_id}&reference_date=2026-06-15"
    ).json()["data"]["transactions"]
    carrefour = next(t for t in transactions if t["payee"] == "CARREFOUR MARKET")
    assert [t["tag_id"] for t in carrefour["tags"]] == [tag_id]
