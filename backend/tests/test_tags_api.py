import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, get_db
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_tags_api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_tags_on_empty_db_returns_empty_list(client):
    response = client.get("/tags")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_post_tag_without_parent_creates_level_1(client):
    response = client.post("/tags", json={"name": "Alimentation"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["level"] == 1
    assert data["parent_id"] is None

    list_response = client.get("/tags")
    assert [t["name"] for t in list_response.json()["data"]] == ["Alimentation"]


def test_post_tag_with_level_1_parent_creates_level_2(client):
    parent_id = client.post("/tags", json={"name": "Alimentation"}).json()["data"]["tag_id"]
    response = client.post("/tags", json={"name": "Courses", "parent_id": parent_id})
    assert response.status_code == 200
    assert response.json()["data"]["level"] == 2


def test_post_tag_with_level_2_parent_creates_level_3(client):
    l1 = client.post("/tags", json={"name": "Alimentation"}).json()["data"]["tag_id"]
    l2 = client.post("/tags", json={"name": "Courses", "parent_id": l1}).json()["data"]["tag_id"]
    response = client.post("/tags", json={"name": "Bio", "parent_id": l2})
    assert response.status_code == 200
    assert response.json()["data"]["level"] == 3


def test_post_tag_with_level_3_parent_returns_422(client):
    l1 = client.post("/tags", json={"name": "Alimentation"}).json()["data"]["tag_id"]
    l2 = client.post("/tags", json={"name": "Courses", "parent_id": l1}).json()["data"]["tag_id"]
    l3 = client.post("/tags", json={"name": "Bio", "parent_id": l2}).json()["data"]["tag_id"]
    response = client.post("/tags", json={"name": "Niveau 4", "parent_id": l3})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_post_tag_with_nonexistent_parent_returns_422(client):
    response = client.post("/tags", json={"name": "Orphelin", "parent_id": 999})
    assert response.status_code == 422


def test_post_tag_blank_name_returns_422(client):
    response = client.post("/tags", json={"name": "   "})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_put_tag_renames_and_preserves_parent_and_level(client):
    parent_id = client.post("/tags", json={"name": "Alimentation"}).json()["data"]["tag_id"]
    child_id = client.post("/tags", json={"name": "Courses", "parent_id": parent_id}).json()["data"]["tag_id"]

    response = client.put(f"/tags/{child_id}", json={"name": "Courses alimentaires"})
    assert response.status_code == 200

    tags = client.get("/tags").json()["data"]
    child = next(t for t in tags if t["tag_id"] == child_id)
    assert child["name"] == "Courses alimentaires"
    assert child["parent_id"] == parent_id
    assert child["level"] == 2


def test_put_tag_nonexistent_returns_404(client):
    response = client.put("/tags/999", json={"name": "Test"})
    assert response.status_code == 404


def test_put_tag_blank_name_returns_422(client):
    tag_id = client.post("/tags", json={"name": "Alimentation"}).json()["data"]["tag_id"]
    response = client.put(f"/tags/{tag_id}", json={"name": "   "})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_delete_tag_without_children_returns_200_and_removes_it(client):
    tag_id = client.post("/tags", json={"name": "Sport"}).json()["data"]["tag_id"]
    response = client.delete(f"/tags/{tag_id}")
    assert response.status_code == 200
    assert response.json()["data"] is None

    tags = client.get("/tags").json()["data"]
    assert tag_id not in [t["tag_id"] for t in tags]


def test_delete_tag_with_children_returns_422_and_keeps_tags(client):
    parent_id = client.post("/tags", json={"name": "Alimentation"}).json()["data"]["tag_id"]
    child_id = client.post("/tags", json={"name": "Courses", "parent_id": parent_id}).json()["data"]["tag_id"]

    response = client.delete(f"/tags/{parent_id}")
    assert response.status_code == 422

    tags = client.get("/tags").json()["data"]
    tag_ids = [t["tag_id"] for t in tags]
    assert parent_id in tag_ids
    assert child_id in tag_ids


def test_delete_tag_nonexistent_returns_404(client):
    response = client.delete("/tags/999")
    assert response.status_code == 404
