import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_budget_api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session_local() as session:
        session.add_all(
            [
                Account(name="Personnel-Lui", is_common=False, start_day=1),
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


def _account_ids(client):
    accounts = client.get("/accounts").json()["data"]
    personal = next(a for a in accounts if not a["is_common"])
    common = next(a for a in accounts if a["is_common"])
    return personal["account_id"], common["account_id"]


def test_put_salaire_reference_returns_200(client):
    personal_id, _ = _account_ids(client)
    response = client.put(
        "/revenues/salaire",
        json={"account_id": personal_id, "period_start": None, "amount": 2500.00},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["period_start"] is None
    assert data["kind"] == "salaire"
    assert data["amount"] == 2500.0


def test_put_salaire_on_common_account_returns_422(client):
    _, common_id = _account_ids(client)
    response = client.put(
        "/revenues/salaire",
        json={"account_id": common_id, "period_start": None, "amount": 2500.00},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_put_salaire_unknown_account_returns_404(client):
    response = client.put(
        "/revenues/salaire",
        json={"account_id": 999, "period_start": None, "amount": 2500.00},
    )
    assert response.status_code == 404


def test_put_salaire_non_positive_amount_returns_422(client):
    personal_id, _ = _account_ids(client)
    response = client.put(
        "/revenues/salaire",
        json={"account_id": personal_id, "period_start": None, "amount": 0},
    )
    assert response.status_code == 422


def test_delete_salaire_correction_not_found_returns_404(client):
    personal_id, _ = _account_ids(client)
    response = client.request(
        "DELETE",
        "/revenues/salaire",
        params={"account_id": personal_id, "period_start": "2026-08-01"},
    )
    assert response.status_code == 404


def test_delete_salaire_correction_reverts_to_reference(client):
    personal_id, _ = _account_ids(client)
    client.put(
        "/revenues/salaire",
        json={"account_id": personal_id, "period_start": None, "amount": 2500.00},
    )
    client.put(
        "/revenues/salaire",
        json={"account_id": personal_id, "period_start": "2026-08-01", "amount": 1000.00},
    )
    response = client.request(
        "DELETE",
        "/revenues/salaire",
        params={"account_id": personal_id, "period_start": "2026-08-01"},
    )
    assert response.status_code == 200
    summary = client.get(
        "/revenues/period",
        params={"account_id": personal_id, "period_start": "2026-08-01"},
    ).json()["data"]
    assert summary["effective_salary"] == 2500.0
    assert summary["has_correction"] is False


def test_post_one_off_and_get_period_summary(client):
    personal_id, _ = _account_ids(client)
    client.put(
        "/revenues/salaire",
        json={"account_id": personal_id, "period_start": None, "amount": 2500.00},
    )
    response = client.post(
        "/revenues/one-off",
        json={
            "account_id": personal_id,
            "period_start": "2026-07-01",
            "amount": 300.00,
            "description": "Prime",
        },
    )
    assert response.status_code == 200
    revenue_id = response.json()["data"]["revenue_id"]

    summary_response = client.get(
        "/revenues/period",
        params={"account_id": personal_id, "period_start": "2026-07-01"},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()["data"]
    assert summary["reference_amount"] == 2500.0
    assert summary["effective_salary"] == 2500.0
    assert len(summary["one_off"]) == 1
    assert summary["total"] == 2800.0

    delete_response = client.delete(f"/revenues/one-off/{revenue_id}")
    assert delete_response.status_code == 200

    summary_after = client.get(
        "/revenues/period",
        params={"account_id": personal_id, "period_start": "2026-07-01"},
    ).json()["data"]
    assert summary_after["one_off"] == []
    assert summary_after["total"] == 2500.0


def test_post_one_off_blank_description_returns_422(client):
    personal_id, _ = _account_ids(client)
    response = client.post(
        "/revenues/one-off",
        json={
            "account_id": personal_id,
            "period_start": "2026-07-01",
            "amount": 300.00,
            "description": "   ",
        },
    )
    assert response.status_code == 422


def test_delete_one_off_not_found_returns_404(client):
    response = client.delete("/revenues/one-off/999")
    assert response.status_code == 404


def test_get_period_summary_on_common_account_returns_422(client):
    _, common_id = _account_ids(client)
    response = client.get(
        "/revenues/period",
        params={"account_id": common_id, "period_start": "2026-07-01"},
    )
    assert response.status_code == 422
