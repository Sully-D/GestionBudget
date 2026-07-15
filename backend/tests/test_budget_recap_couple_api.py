from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_budget_recap_couple_api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session_local() as session:
        lui = Account(name="Personnel-Lui", is_common=False, start_day=1)
        elle = Account(name="Personnel-Elle", is_common=False, start_day=1)
        commun = Account(name="Commun", is_common=True, start_day=1)
        session.add_all([lui, elle, commun])
        session.commit()
        session.refresh(lui)
        session.refresh(elle)
        session.refresh(commun)

        revenus = Tag(name="Revenus", parent_id=None, level=1)
        charges = Tag(name="Charges", parent_id=None, level=1)
        virements = Tag(name="Virements compte commun", parent_id=None, level=1)
        investissements = Tag(name="Investissements", parent_id=None, level=1)
        session.add_all([revenus, charges, virements, investissements])
        session.commit()
        for t in (revenus, charges, virements, investissements):
            session.refresh(t)

        today = date.today()
        current_month_start = today.replace(day=1)
        last_month_start = (
            date(current_month_start.year - 1, 12, 1)
            if current_month_start.month == 1
            else date(current_month_start.year, current_month_start.month - 1, 1)
        )
        tx = Transaction(
            account_id=lui.account_id, date=last_month_start, amount=Decimal("2000.00"), label="Salaire"
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)
        session.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=revenus.tag_id))
        session.commit()

        state = {
            "lui_id": lui.account_id,
            "elle_id": elle.account_id,
            "commun_id": commun.account_id,
        }

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), state
    app.dependency_overrides.clear()


def test_get_recap_couple_returns_data_envelope(client):
    test_client, state = client
    response = test_client.get(
        "/budget/recap-couple", params={"account_id": state["commun_id"], "months": 1}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["months"] == 1
    assert data["couple_charges_percentage"] is None
    lui_row = next(r for r in data["rows"] if r["account_id"] == state["lui_id"])
    assert lui_row["revenus"] == 2000.0


def test_get_recap_couple_months_zero_returns_422(client):
    test_client, state = client
    response = test_client.get(
        "/budget/recap-couple", params={"account_id": state["commun_id"], "months": 0}
    )
    assert response.status_code == 422


def test_get_recap_couple_months_above_120_returns_422_not_500(client):
    test_client, state = client
    response = test_client.get(
        "/budget/recap-couple", params={"account_id": state["commun_id"], "months": 100000}
    )
    assert response.status_code == 422


def test_get_recap_couple_months_not_integer_returns_422(client):
    test_client, state = client
    response = test_client.get(
        "/budget/recap-couple", params={"account_id": state["commun_id"], "months": "abc"}
    )
    assert response.status_code == 422


def test_get_recap_couple_months_missing_returns_422(client):
    test_client, state = client
    response = test_client.get(
        "/budget/recap-couple", params={"account_id": state["commun_id"]}
    )
    assert response.status_code == 422


def test_patch_percentage_then_get_reflects_persisted_value(client):
    test_client, state = client
    patch_response = test_client.patch(
        "/budget/couple-charges-percentage",
        json={"account_id": state["commun_id"], "percentage": 40},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["couple_charges_percentage"] == 40.0

    get_response = test_client.get(
        "/budget/recap-couple", params={"account_id": state["commun_id"], "months": 1}
    )
    data = get_response.json()["data"]
    assert data["couple_charges_percentage"] == 40.0
    assert data["budget_charges_convenu"] == 800.0
    assert data["reste_disponible"] == 1200.0


def test_patch_percentage_over_100_returns_422(client):
    test_client, state = client
    response = test_client.patch(
        "/budget/couple-charges-percentage",
        json={"account_id": state["commun_id"], "percentage": 150},
    )
    assert response.status_code == 422


def test_patch_percentage_negative_returns_422(client):
    test_client, state = client
    response = test_client.patch(
        "/budget/couple-charges-percentage",
        json={"account_id": state["commun_id"], "percentage": -5},
    )
    assert response.status_code == 422


def test_patch_percentage_on_non_common_account_returns_422(client):
    test_client, state = client
    response = test_client.patch(
        "/budget/couple-charges-percentage",
        json={"account_id": state["lui_id"], "percentage": 40},
    )
    assert response.status_code == 422


def test_get_recap_couple_missing_tag_returns_422_naming_tag(client):
    test_client, state = client
    db = next(app.dependency_overrides[get_db]())
    db.query(Tag).filter(Tag.name == "Investissements").delete()
    db.commit()
    db.close()

    response = test_client.get(
        "/budget/recap-couple", params={"account_id": state["commun_id"], "months": 1}
    )
    assert response.status_code == 422
    assert "Investissements" in response.json()["detail"]
