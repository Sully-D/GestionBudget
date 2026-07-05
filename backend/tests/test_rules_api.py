import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, get_db
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_rules_api.db"
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


@pytest.fixture
def tag_id(client):
    return client.post("/tags", json={"name": "Alimentation"}).json()["data"]["tag_id"]


@pytest.fixture
def other_tag_id(client):
    return client.post("/tags", json={"name": "Loisirs"}).json()["data"]["tag_id"]


def test_get_rules_on_empty_db_returns_empty_list(client):
    response = client.get("/rules")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_post_rule_label_contains_valid(client, tag_id):
    response = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "Carrefour", "tag_id": tag_id},
    )
    assert response.status_code == 200
    assert response.json()["data"]["sort_order"] == 1


def test_post_rule_payee_exact_valid(client, tag_id):
    response = client.post(
        "/rules",
        json={"condition_type": "payee_exact", "condition_value": "EDF", "tag_id": tag_id},
    )
    assert response.status_code == 200


def test_post_rule_second_time_has_sort_order_2(client, tag_id):
    client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "A", "tag_id": tag_id},
    )
    response = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "B", "tag_id": tag_id},
    )
    assert response.json()["data"]["sort_order"] == 2


def test_post_rule_invalid_condition_type_returns_422(client, tag_id):
    response = client.post(
        "/rules",
        json={"condition_type": "invalid_type", "condition_value": "A", "tag_id": tag_id},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_post_rule_with_nonexistent_tag_returns_422(client):
    response = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "A", "tag_id": 999},
    )
    assert response.status_code == 422


def test_post_rule_blank_condition_value_returns_422(client, tag_id):
    response = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "   ", "tag_id": tag_id},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_put_rule_modifies_rule(client, tag_id, other_tag_id):
    rule_id = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "A", "tag_id": tag_id},
    ).json()["data"]["rule_id"]

    response = client.put(
        f"/rules/{rule_id}",
        json={"condition_type": "payee_exact", "condition_value": "B", "tag_id": other_tag_id},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["condition_type"] == "payee_exact"
    assert data["condition_value"] == "B"
    assert data["tag_id"] == other_tag_id


def test_put_rule_nonexistent_returns_404(client, tag_id):
    response = client.put(
        "/rules/999",
        json={"condition_type": "label_contains", "condition_value": "A", "tag_id": tag_id},
    )
    assert response.status_code == 404


def test_delete_rule_returns_200_and_removes_it(client, tag_id):
    rule_id = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "A", "tag_id": tag_id},
    ).json()["data"]["rule_id"]

    response = client.delete(f"/rules/{rule_id}")
    assert response.status_code == 200
    assert response.json()["data"] is None

    rules = client.get("/rules").json()["data"]
    assert rule_id not in [r["rule_id"] for r in rules]


def test_delete_rule_nonexistent_returns_404(client):
    response = client.delete("/rules/999")
    assert response.status_code == 404


def test_put_rules_reorder_valid_new_order(client, tag_id):
    r1 = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "A", "tag_id": tag_id},
    ).json()["data"]["rule_id"]
    r2 = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "B", "tag_id": tag_id},
    ).json()["data"]["rule_id"]

    response = client.put("/rules/reorder", json={"rule_ids": [r2, r1]})
    assert response.status_code == 200
    data = response.json()["data"]
    assert [r["rule_id"] for r in data] == [r2, r1]
    assert [r["sort_order"] for r in data] == [1, 2]


def test_put_rules_reorder_missing_extra_or_duplicate_id_returns_422(client, tag_id):
    r1 = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "A", "tag_id": tag_id},
    ).json()["data"]["rule_id"]
    r2 = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "B", "tag_id": tag_id},
    ).json()["data"]["rule_id"]

    missing = client.put("/rules/reorder", json={"rule_ids": [r1]})
    assert missing.status_code == 422

    extra = client.put("/rules/reorder", json={"rule_ids": [r1, r2, 999]})
    assert extra.status_code == 422

    duplicate = client.put("/rules/reorder", json={"rule_ids": [r1, r1]})
    assert duplicate.status_code == 422


def test_put_rules_reorder_route_does_not_collide_with_rule_id_route(client, tag_id):
    # Non-régression : sans le convertisseur `:int` sur `{rule_id}`, ce PUT
    # matcherait `/rules/{rule_id}` avec `rule_id="reorder"` (422 de coercion)
    # au lieu d'atteindre le handler dédié `/rules/reorder`.
    r1 = client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "A", "tag_id": tag_id},
    ).json()["data"]["rule_id"]

    response = client.put("/rules/reorder", json={"rule_ids": [r1]})
    assert response.status_code == 200
    assert response.json()["data"][0]["rule_id"] == r1


def test_post_rules_evaluate_label_contains_match(client, tag_id):
    client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "Carrefour", "tag_id": tag_id},
    )
    response = client.post("/rules/evaluate", json={"label": "ACHAT CARREFOUR", "payee": None})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tag_id"] == tag_id
    assert data["condition_type"] == "label_contains"
    assert data["condition_value"] == "Carrefour"


def test_post_rules_evaluate_payee_exact_match(client, tag_id):
    client.post(
        "/rules",
        json={"condition_type": "payee_exact", "condition_value": "EDF", "tag_id": tag_id},
    )
    response = client.post("/rules/evaluate", json={"label": "peu importe", "payee": "edf"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tag_id"] == tag_id
    assert data["condition_type"] == "payee_exact"
    assert data["condition_value"] == "EDF"


def test_post_rules_evaluate_no_match_returns_all_none(client, tag_id):
    client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "Carrefour", "tag_id": tag_id},
    )
    response = client.post("/rules/evaluate", json={"label": "ACHAT LECLERC", "payee": None})
    assert response.status_code == 200
    assert response.json()["data"] == {
        "tag_id": None,
        "condition_type": None,
        "condition_value": None,
    }


def test_post_rules_evaluate_multiple_matches_returns_first_by_sort_order(
    client, tag_id, other_tag_id
):
    client.post(
        "/rules",
        json={"condition_type": "label_contains", "condition_value": "achat", "tag_id": tag_id},
    )
    client.post(
        "/rules",
        json={
            "condition_type": "label_contains",
            "condition_value": "carrefour",
            "tag_id": other_tag_id,
        },
    )
    response = client.post("/rules/evaluate", json={"label": "ACHAT CARREFOUR", "payee": None})
    assert response.status_code == 200
    assert response.json()["data"]["tag_id"] == tag_id


def test_post_rules_evaluate_blank_label_and_no_payee_does_not_raise(client):
    response = client.post("/rules/evaluate", json={"label": "", "payee": None})
    assert response.status_code == 200
    assert response.json()["data"]["tag_id"] is None
