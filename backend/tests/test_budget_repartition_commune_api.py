from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.model import Revenue
from app.core.db import Base, get_db
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag
from main import app

PERIOD_START = date(2026, 3, 1)


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_budget_repartition_commune_api.db"
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

        tag = Tag(name="Charges", parent_id=None, level=1)
        session.add(tag)
        session.commit()
        session.refresh(tag)

        session.add(
            Revenue(account_id=lui.account_id, period_start=None, kind="salaire", amount=Decimal("2000.00"))
        )
        session.add(
            Revenue(account_id=elle.account_id, period_start=None, kind="salaire", amount=Decimal("1000.00"))
        )
        session.commit()

        tx_lui = Transaction(
            account_id=lui.account_id, date=date(2026, 3, 5), amount=Decimal("-500.00"), label="Loyer"
        )
        tx_elle = Transaction(
            account_id=elle.account_id, date=date(2026, 3, 5), amount=Decimal("-200.00"), label="Loyer"
        )
        session.add_all([tx_lui, tx_elle])
        session.commit()
        session.refresh(tx_lui)
        session.refresh(tx_elle)

        session.add_all(
            [
                TransactionTag(transaction_id=tx_lui.transaction_id, tag_id=tag.tag_id),
                TransactionTag(transaction_id=tx_elle.transaction_id, tag_id=tag.tag_id),
            ]
        )
        session.commit()

        state = {
            "lui_id": lui.account_id,
            "elle_id": elle.account_id,
            "commun_id": commun.account_id,
            "tag_id": tag.tag_id,
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


def test_get_repartition_commune_returns_data_envelope(client):
    test_client, state = client
    response = test_client.get(
        "/repartition-commune",
        params={
            "montant_total": "1000.00",
            "tag_id": state["tag_id"],
            "period_start": PERIOD_START.isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["tag_id"] == state["tag_id"]
    assert data["montant_total"] == 1000.0
    assert isinstance(data["montant_total"], float)
    assert len(data["parts"]) == 2
    total_part = sum(p["part"] for p in data["parts"])
    assert round(total_part, 2) == 1000.0


def test_get_repartition_commune_unknown_tag_returns_404(client):
    test_client, state = client
    response = test_client.get(
        "/repartition-commune",
        params={
            "montant_total": "1000.00",
            "tag_id": 999,
            "period_start": PERIOD_START.isoformat(),
        },
    )
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_get_repartition_commune_reste_a_vivre_negatif_ou_nul_returns_422(client):
    test_client, state = client

    # Force un RàV négatif sur un nouveau Tag dédié (charges > revenus de 2000),
    # sans modifier la fixture du Tag "Charges" partagé par les autres tests.
    db = next(app.dependency_overrides[get_db]())
    tag2 = Tag(name="Charges2", parent_id=None, level=1)
    db.add(tag2)
    db.commit()
    db.refresh(tag2)
    tx = Transaction(
        account_id=state["lui_id"], date=date(2026, 3, 6), amount=Decimal("-2500.00"), label="Grosse dépense"
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag2.tag_id))
    db.commit()
    tag2_id = tag2.tag_id
    db.close()

    response = test_client.get(
        "/repartition-commune",
        params={
            "montant_total": "1000.00",
            "tag_id": tag2_id,
            "period_start": PERIOD_START.isoformat(),
        },
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_get_repartition_commune_montant_total_absent_returns_422(client):
    test_client, state = client
    response = test_client.get(
        "/repartition-commune",
        params={"tag_id": state["tag_id"], "period_start": PERIOD_START.isoformat()},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_get_repartition_commune_montant_total_non_positif_returns_422(client):
    test_client, state = client
    response = test_client.get(
        "/repartition-commune",
        params={
            "montant_total": "0",
            "tag_id": state["tag_id"],
            "period_start": PERIOD_START.isoformat(),
        },
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
