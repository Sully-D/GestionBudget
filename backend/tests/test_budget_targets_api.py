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
    db_path = tmp_path / "test_budget_targets_api.db"
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
        session.add(Tag(name="Alimentation", parent_id=None, level=1))
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


def test_put_budget_target_returns_200(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.put(
        "/budget-targets",
        json={"account_id": personal_id, "tag_id": tag_id, "percentage": 15.00},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["account_id"] == personal_id
    assert data["tag_id"] == tag_id
    assert data["percentage"] == 15.0


def test_put_budget_target_on_common_account_returns_422(client):
    _, common_id = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.put(
        "/budget-targets",
        json={"account_id": common_id, "tag_id": tag_id, "percentage": 15.00},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_put_budget_target_unknown_tag_returns_404(client):
    personal_id, _ = _account_ids(client)
    response = client.put(
        "/budget-targets",
        json={"account_id": personal_id, "tag_id": 999, "percentage": 15.00},
    )
    assert response.status_code == 404


def test_put_budget_target_unknown_account_returns_404(client):
    tag_id = _tag_id(client)
    response = client.put(
        "/budget-targets",
        json={"account_id": 999, "tag_id": tag_id, "percentage": 15.00},
    )
    assert response.status_code == 404


def test_put_budget_target_percentage_over_100_returns_422(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.put(
        "/budget-targets",
        json={"account_id": personal_id, "tag_id": tag_id, "percentage": 150.00},
    )
    assert response.status_code == 422


def test_put_budget_target_non_positive_percentage_returns_422(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.put(
        "/budget-targets",
        json={"account_id": personal_id, "tag_id": tag_id, "percentage": 0},
    )
    assert response.status_code == 422


def test_put_budget_target_percentage_exactly_100_returns_200(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    response = client.put(
        "/budget-targets",
        json={"account_id": personal_id, "tag_id": tag_id, "percentage": 100.00},
    )
    assert response.status_code == 200
    assert response.json()["data"]["percentage"] == 100.0


def test_get_budget_targets_returns_only_matching_account(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    client.put(
        "/budget-targets",
        json={"account_id": personal_id, "tag_id": tag_id, "percentage": 15.00},
    )
    response = client.get("/budget-targets", params={"account_id": personal_id})
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["tag_id"] == tag_id


def test_get_budget_targets_on_common_account_returns_422(client):
    _, common_id = _account_ids(client)
    response = client.get("/budget-targets", params={"account_id": common_id})
    assert response.status_code == 422


def test_delete_budget_target_returns_200_then_404(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    create_response = client.put(
        "/budget-targets",
        json={"account_id": personal_id, "tag_id": tag_id, "percentage": 15.00},
    )
    target_id = create_response.json()["data"]["target_id"]

    delete_response = client.delete(f"/budget-targets/{target_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] is None

    second_delete = client.delete(f"/budget-targets/{target_id}")
    assert second_delete.status_code == 404


def test_delete_budget_target_unknown_id_returns_404(client):
    response = client.delete("/budget-targets/999")
    assert response.status_code == 404
