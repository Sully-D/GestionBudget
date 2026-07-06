import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from app.tags.model import Tag
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_planned_expenses_api.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session_local() as session:
        session.add_all(
            [
                Account(name="Personnel-Lui", is_common=False, start_day=1),
                Account(name="Commun", is_common=True, start_day=1),
            ]
        )
        session.add(Tag(name="Loisirs", parent_id=None, level=1))
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


def _tag_id(client):
    tags = client.get("/tags").json()["data"]
    return tags[0]["tag_id"]


def test_post_planned_expense_returns_data_envelope(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.post(
        "/planned-expenses",
        json={
            "account_id": personal_id,
            "tag_id": tag_id,
            "date": "2026-08-15",
            "amount": -120.00,
            "description": "Vacances",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data["amount"], float)
    assert data["series_id"] is None


def test_post_planned_expense_split_returns_list_envelope(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.post(
        "/planned-expenses/split",
        json={
            "account_id": personal_id,
            "tag_id": tag_id,
            "start_date": "2026-01-10",
            "total_amount": 300.00,
            "total_periods": 3,
            "description": "Ventilée",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 3
    assert len({item["series_id"] for item in data}) == 1


def test_get_planned_expenses_returns_data_envelope(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    client.post(
        "/planned-expenses",
        json={
            "account_id": personal_id,
            "tag_id": tag_id,
            "date": "2026-08-15",
            "amount": -120.00,
            "description": "Vacances",
        },
    )
    response = client.get("/planned-expenses", params={"account_id": personal_id})
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_put_planned_expense_unknown_id_returns_404(client):
    tag_id = _tag_id(client)
    response = client.put(
        "/planned-expenses/999",
        json={
            "date": "2026-08-15",
            "amount": -50.00,
            "tag_id": tag_id,
            "description": "X",
        },
    )
    assert response.status_code == 404


def test_delete_planned_expense_returns_200_then_404(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    create_response = client.post(
        "/planned-expenses",
        json={
            "account_id": personal_id,
            "tag_id": tag_id,
            "date": "2026-08-15",
            "amount": -120.00,
            "description": "Vacances",
        },
    )
    expense_id = create_response.json()["data"]["expense_id"]

    delete_response = client.delete(f"/planned-expenses/{expense_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] is None

    second_delete = client.delete(f"/planned-expenses/{expense_id}")
    assert second_delete.status_code == 404


def test_post_planned_expense_on_common_account_returns_422(client):
    _, common_id = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.post(
        "/planned-expenses",
        json={
            "account_id": common_id,
            "tag_id": tag_id,
            "date": "2026-08-15",
            "amount": -120.00,
            "description": "Vacances",
        },
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_post_planned_expense_positive_amount_returns_422(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.post(
        "/planned-expenses",
        json={
            "account_id": personal_id,
            "tag_id": tag_id,
            "date": "2026-08-15",
            "amount": 120.00,
            "description": "Vacances",
        },
    )
    assert response.status_code == 422
