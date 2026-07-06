from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from app.transactions.model import Transaction
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_rapprochement_api.db"
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
        session.commit()
        personal = session.query(Account).filter_by(is_common=False).first()
        session.add(
            Transaction(
                account_id=personal.account_id,
                date=date(2026, 1, 5),
                amount=Decimal("-50.00"),
                label="Salle de sport",
            )
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


def _account_id(client):
    accounts = client.get("/accounts").json()["data"]
    return next(a for a in accounts if not a["is_common"])["account_id"]


def _confirm_recurring(client, account_id):
    response = client.post(
        "/recurring/confirm",
        json={
            "account_id": account_id,
            "signature": "salle de sport",
            "label": "Salle de sport",
            "amount": -50.00,
            "periodicity": "mensuelle",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["recurring_id"]


def test_post_transaction_matching_recurring_creates_pending_rapprochement(client):
    account_id = _account_id(client)
    _confirm_recurring(client, account_id)

    response = client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-02-05",
            "amount": -50.00,
            "label": "Salle de sport",
        },
    )
    assert response.status_code == 200

    pending = client.get("/rapprochement/pending", params={"account_id": account_id})
    assert pending.status_code == 200
    data = pending.json()["data"]
    assert len(data) == 1
    entry = data[0]
    assert entry["recurring_label"] == "Salle de sport"
    assert entry["recurring_periodicity"] == "mensuelle"
    assert entry["transaction_date"] == "2026-02-05"
    assert isinstance(entry["transaction_amount"], float)
    assert entry["transaction_amount"] == -50.0
    assert entry["transaction_label"] == "Salle de sport"


def test_post_confirm_rapprochement_returns_data_envelope(client):
    account_id = _account_id(client)
    _confirm_recurring(client, account_id)
    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-02-05",
            "amount": -50.00,
            "label": "Salle de sport",
        },
    )
    match_id = client.get(
        "/rapprochement/pending", params={"account_id": account_id}
    ).json()["data"][0]["match_id"]

    response = client.post(f"/rapprochement/{match_id}/confirm")
    assert response.status_code == 200
    assert response.json()["data"] == {"match_id": match_id, "status": "confirmed"}

    pending_after = client.get("/rapprochement/pending", params={"account_id": account_id})
    assert pending_after.json()["data"] == []


def test_post_confirm_rapprochement_unknown_id_returns_404(client):
    response = client.post("/rapprochement/999/confirm")
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_post_confirm_rapprochement_already_confirmed_returns_422(client):
    account_id = _account_id(client)
    _confirm_recurring(client, account_id)
    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-02-05",
            "amount": -50.00,
            "label": "Salle de sport",
        },
    )
    match_id = client.get(
        "/rapprochement/pending", params={"account_id": account_id}
    ).json()["data"][0]["match_id"]
    client.post(f"/rapprochement/{match_id}/confirm")

    response = client.post(f"/rapprochement/{match_id}/confirm")
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_delete_rapprochement_rejects_it_and_returns_data_none(client):
    account_id = _account_id(client)
    _confirm_recurring(client, account_id)
    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-02-05",
            "amount": -50.00,
            "label": "Salle de sport",
        },
    )
    match_id = client.get(
        "/rapprochement/pending", params={"account_id": account_id}
    ).json()["data"][0]["match_id"]

    response = client.delete(f"/rapprochement/{match_id}")
    assert response.status_code == 200
    assert response.json()["data"] is None

    pending_after = client.get("/rapprochement/pending", params={"account_id": account_id})
    assert pending_after.json()["data"] == []


def test_delete_rapprochement_unknown_id_returns_404(client):
    response = client.delete("/rapprochement/999")
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_get_pending_rapprochements_unknown_account_returns_404(client):
    response = client.get("/rapprochement/pending", params={"account_id": 999})
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_get_pending_rapprochements_skips_orphaned_match_without_crashing(client):
    account_id = _account_id(client)
    _confirm_recurring(client, account_id)
    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-02-05",
            "amount": -50.00,
            "label": "Salle de sport",
        },
    )
    transaction_id = client.get(
        "/rapprochement/pending", params={"account_id": account_id}
    ).json()["data"][0]["transaction_id"]

    session = next(app.dependency_overrides[get_db]())
    try:
        session.delete(session.get(Transaction, transaction_id))
        session.commit()
    finally:
        session.close()

    response = client.get("/rapprochement/pending", params={"account_id": account_id})
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_post_transaction_without_match_creates_no_rapprochement(client):
    account_id = _account_id(client)
    _confirm_recurring(client, account_id)

    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-02-05",
            "amount": -50.00,
            "label": "Sans rapport",
        },
    )

    pending = client.get("/rapprochement/pending", params={"account_id": account_id})
    assert pending.json()["data"] == []
