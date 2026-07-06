from datetime import date, timedelta

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
    db_path = tmp_path / "test_projection_api.db"
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


def test_get_projection_returns_data_envelope_with_planned_expense(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    today = date.today().isoformat()
    client.post(
        "/planned-expenses",
        json={
            "account_id": personal_id,
            "tag_id": tag_id,
            "date": today,
            "amount": -50.00,
            "description": "Cadeau",
        },
    )
    response = client.get("/projection", params={"account_id": personal_id})
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["type"] == "planifiee"
    assert isinstance(data[0]["amount"], float)


def test_get_projection_default_horizon_is_three_months(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    far_date = (date.today() + timedelta(days=200)).isoformat()
    client.post(
        "/planned-expenses",
        json={
            "account_id": personal_id,
            "tag_id": tag_id,
            "date": far_date,
            "amount": -50.00,
            "description": "Hors 3 mois",
        },
    )
    response = client.get("/projection", params={"account_id": personal_id})
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_get_projection_explicit_valid_horizon_returns_200(client):
    personal_id, _ = _account_ids(client)
    for horizon in (1, 3, 6):
        response = client.get(
            "/projection", params={"account_id": personal_id, "horizon_months": horizon}
        )
        assert response.status_code == 200


def test_get_projection_invalid_horizon_returns_422(client):
    personal_id, _ = _account_ids(client)
    response = client.get(
        "/projection", params={"account_id": personal_id, "horizon_months": 2}
    )
    assert response.status_code == 422


def test_get_projection_on_common_account_returns_422(client):
    _, common_id = _account_ids(client)
    response = client.get("/projection", params={"account_id": common_id})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_get_projection_without_account_id_returns_422(client):
    response = client.get("/projection")
    assert response.status_code == 422


def test_get_projection_without_account_id_but_html_accept_serves_frontend(client):
    # Collision de route : le chemin frontend `/projection` est identique au
    # chemin API GET `/projection`. Une navigation directe/rafraîchissement du
    # navigateur (Accept: text/html, pas d'account_id) doit servir la SPA, pas
    # l'erreur 422 destinée aux appels API.
    response = client.get("/projection", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_get_projection_without_account_id_low_priority_html_accept_returns_422(client):
    response = client.get(
        "/projection", headers={"accept": "application/json, text/html;q=0.1"}
    )
    assert response.status_code == 422


def test_get_projection_html_accept_missing_frontend_index_returns_404(client, monkeypatch):
    import app.projections.projection_router as projection_router

    monkeypatch.setattr(
        projection_router, "FRONTEND_INDEX", projection_router.Path("does/not/exist.html")
    )
    response = client.get("/projection", headers={"accept": "text/html"})
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
