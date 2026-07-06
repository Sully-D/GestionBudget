from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.model import Revenue
from app.core.db import Base, get_db
from app.transactions.model import Transaction
from main import app

PERIOD_START = date(2026, 3, 1)


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_budget_disponible_api.db"
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
        session.add(
            Transaction(
                account_id=personal.account_id,
                date=date(2026, 3, 10),
                amount=Decimal("-42.00"),
                label="Courses",
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


def test_get_disponible_returns_data_envelope(client):
    test_client, state = client
    response = test_client.get(
        "/disponible",
        params={"account_id": state["personal_id"], "period_start": PERIOD_START.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["account_id"] == state["personal_id"]
    assert data["period_start"] == "2026-03-01"
    assert data["period_end"] == "2026-03-31"
    assert data["revenus"] == 1000.0
    assert isinstance(data["revenus"], float)
    assert data["charges_recurrentes"] == 0.0
    assert data["depenses_planifiees"] == 0.0
    assert data["depenses_courantes"] == 42.0
    assert data["disponible"] == 958.0


def test_get_disponible_on_common_account_returns_422(client):
    test_client, state = client
    response = test_client.get(
        "/disponible",
        params={"account_id": state["common_id"], "period_start": PERIOD_START.isoformat()},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_get_disponible_unknown_account_returns_404(client):
    test_client, state = client
    response = test_client.get(
        "/disponible",
        params={"account_id": 999, "period_start": PERIOD_START.isoformat()},
    )
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
