import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_accounts.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session_local() as session:
        session.add_all(
            [
                Account(name="Personnel-Lui", is_common=False, start_day=1),
                Account(name="Personnel-Elle", is_common=False, start_day=1),
                Account(name="Commun", is_common=True, start_day=1),
            ]
        )
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


def test_get_accounts_returns_three_accounts(client):
    response = client.get("/accounts")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 3
    assert [a["name"] for a in data] == ["Personnel-Lui", "Personnel-Elle", "Commun"]
    assert all(a["balance"] == 0 for a in data)


def test_get_account_by_id_not_found_returns_404(client):
    response = client.get("/accounts/999")
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_get_account_by_id_returns_account(client):
    accounts = client.get("/accounts").json()["data"]
    account_id = accounts[0]["account_id"]
    response = client.get(f"/accounts/{account_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["account_id"] == account_id
    assert data["name"] == accounts[0]["name"]


def test_put_account_start_day_out_of_range_returns_422(client):
    accounts = client.get("/accounts").json()["data"]
    account_id = accounts[0]["account_id"]
    response = client.put(f"/accounts/{account_id}", json={"start_day": 35})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_put_account_start_day_null_returns_422(client):
    accounts = client.get("/accounts").json()["data"]
    account_id = accounts[0]["account_id"]
    response = client.put(f"/accounts/{account_id}", json={"start_day": None})
    assert response.status_code == 422


def test_put_account_reference_balance_without_date_returns_422(client):
    accounts = client.get("/accounts").json()["data"]
    account_id = accounts[0]["account_id"]
    response = client.put(f"/accounts/{account_id}", json={"reference_balance": 100})
    assert response.status_code == 422


def test_put_account_reference_date_without_balance_returns_422(client):
    accounts = client.get("/accounts").json()["data"]
    account_id = accounts[0]["account_id"]
    response = client.put(
        f"/accounts/{account_id}", json={"reference_date": "2026-07-01"}
    )
    assert response.status_code == 422


def test_put_account_reference_balance_null_with_date_returns_422(client):
    accounts = client.get("/accounts").json()["data"]
    account_id = accounts[0]["account_id"]
    response = client.put(
        f"/accounts/{account_id}",
        json={"reference_balance": None, "reference_date": "2026-07-01"},
    )
    assert response.status_code == 422


def test_put_account_valid_update_recomputes_balance_and_period(client):
    accounts = client.get("/accounts").json()["data"]
    account_id = accounts[0]["account_id"]
    response = client.put(
        f"/accounts/{account_id}",
        json={
            "reference_balance": 847.00,
            "reference_date": "2026-07-01",
            "start_day": 15,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["balance"] == 847.0
    assert data["start_day"] == 15
    assert data["period_start"] is not None
    assert data["period_end"] is not None
