from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.model import Revenue
from app.core.db import Base, get_db
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_budget_disponible_evolution_api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session_local() as session:
        personal = Account(name="Personnel-Lui", is_common=False, start_day=1)
        common = Account(name="Commun", is_common=True, start_day=1)
        session.add_all([personal, common])
        session.commit()
        session.refresh(personal)
        session.refresh(common)

        session.add(
            Revenue(
                account_id=personal.account_id,
                period_start=None,
                kind="salaire",
                amount=Decimal("1000.00"),
            )
        )
        session.commit()

        state = {"personal_id": personal.account_id, "common_id": common.account_id}

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), state
    app.dependency_overrides.clear()


def test_get_disponible_evolution_returns_six_chronological_entries(client):
    test_client, state = client
    response = test_client.get(
        "/disponible-evolution", params={"account_id": state["personal_id"]}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 6

    period_starts = [date.fromisoformat(entry["period_start"]) for entry in data]
    assert period_starts == sorted(period_starts)
    assert len(set(period_starts)) == 6

    # Chaque période est exactement un mois calendaire après la précédente
    # (start_day=1) : détecte un mois sauté ou dupliqué par la marche arrière
    # par curseur, que le simple tri+unicité ci-dessus ne verrait pas.
    month_indices = [d.year * 12 + d.month for d in period_starts]
    assert [b - a for a, b in zip(month_indices, month_indices[1:])] == [1] * 5

    last_entry = data[-1]
    assert last_entry["revenus"] == 1000.0
    assert last_entry["disponible"] == 1000.0

    direct_response = test_client.get(
        "/disponible",
        params={"account_id": state["personal_id"], "period_start": last_entry["period_start"]},
    )
    assert direct_response.status_code == 200
    assert direct_response.json()["data"]["disponible"] == last_entry["disponible"]


def test_get_disponible_evolution_on_common_account_returns_422(client):
    test_client, state = client
    response = test_client.get(
        "/disponible-evolution", params={"account_id": state["common_id"]}
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_get_disponible_evolution_unknown_account_returns_404(client):
    test_client, state = client
    response = test_client.get("/disponible-evolution", params={"account_id": 999})
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
