from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from app.tags.model import Tag
from app.transactions.model import Transaction
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_recurring_api.db"
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
        session.add(Tag(name="Abonnements", parent_id=None, level=1))
        session.commit()
        personal = session.query(Account).filter_by(is_common=False).first()
        for month in (1, 2, 3, 4):
            session.add(
                Transaction(
                    account_id=personal.account_id,
                    date=date(2026, month, 5),
                    amount=-50.00,
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


def _account_ids(client):
    accounts = client.get("/accounts").json()["data"]
    personal = next(a for a in accounts if not a["is_common"])
    common = next(a for a in accounts if a["is_common"])
    return personal["account_id"], common["account_id"]


def _tag_id(client):
    tags = client.get("/tags").json()["data"]
    return tags[0]["tag_id"]


def test_get_recurring_candidates_returns_data_envelope(client):
    personal_id, _ = _account_ids(client)
    response = client.get("/recurring/candidates", params={"account_id": personal_id})
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["periodicity"] == "mensuelle"
    assert isinstance(data[0]["amount"], float)


def test_get_recurring_candidates_on_common_account_returns_422(client):
    _, common_id = _account_ids(client)
    response = client.get("/recurring/candidates", params={"account_id": common_id})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_post_confirm_recurring_returns_data_envelope(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    candidate = client.get(
        "/recurring/candidates", params={"account_id": personal_id}
    ).json()["data"][0]
    response = client.post(
        "/recurring/confirm",
        json={
            "account_id": personal_id,
            "signature": candidate["signature"],
            "label": candidate["label"],
            "amount": candidate["amount"],
            "periodicity": candidate["periodicity"],
            "tag_id": tag_id,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "confirmed"
    assert isinstance(data["amount"], float)


def test_post_reject_recurring_removes_candidate_from_next_call(client):
    personal_id, _ = _account_ids(client)
    candidate = client.get(
        "/recurring/candidates", params={"account_id": personal_id}
    ).json()["data"][0]
    response = client.post(
        "/recurring/reject",
        json={
            "account_id": personal_id,
            "signature": candidate["signature"],
            "label": candidate["label"],
            "amount": candidate["amount"],
            "periodicity": candidate["periodicity"],
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "rejected"

    after = client.get("/recurring/candidates", params={"account_id": personal_id})
    assert after.json()["data"] == []


def test_put_recurring_unknown_id_returns_404(client):
    response = client.put(
        "/recurring/999", json={"amount": -50.00, "periodicity": "mensuelle"}
    )
    assert response.status_code == 404


def test_delete_recurring_returns_200_then_404(client):
    personal_id, _ = _account_ids(client)
    candidate = client.get(
        "/recurring/candidates", params={"account_id": personal_id}
    ).json()["data"][0]
    confirm_response = client.post(
        "/recurring/confirm",
        json={
            "account_id": personal_id,
            "signature": candidate["signature"],
            "label": candidate["label"],
            "amount": candidate["amount"],
            "periodicity": candidate["periodicity"],
        },
    )
    recurring_id = confirm_response.json()["data"]["recurring_id"]

    delete_response = client.delete(f"/recurring/{recurring_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] is None

    second_delete = client.delete(f"/recurring/{recurring_id}")
    assert second_delete.status_code == 404


def _create_current_period_transaction(client, account_id, label="Abonnement Musique"):
    # Le picker de la spec liste les Transactions de la période courante
    # (`getTransactions(accountId)` sans `referenceDate`) : on crée donc la
    # Transaction avec la date du jour plutôt que de réutiliser les Transactions
    # de janvier-avril du fixture, qui servent aux tests de détection de
    # candidates et ne tombent pas forcément dans la période en cours.
    response = client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": date.today().isoformat(),
            "amount": -50.00,
            "label": label,
        },
    )
    return response.json()["data"]


def test_post_create_recurring_from_transaction_returns_data_envelope(client):
    personal_id, _ = _account_ids(client)
    tag_id = _tag_id(client)
    transaction = _create_current_period_transaction(client, personal_id)
    response = client.post(
        "/recurring/from-transaction",
        json={
            "transaction_id": transaction["transaction_id"],
            "label": "Abonnement Musique",
            "amount": -50.00,
            "periodicity": "mensuelle",
            "tag_id": tag_id,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "confirmed"
    assert data["label"] == "Abonnement Musique"
    assert data["tag_id"] == tag_id
    assert isinstance(data["amount"], float)


def test_post_create_recurring_from_transaction_duplicate_signature_returns_422(client):
    personal_id, _ = _account_ids(client)
    first = _create_current_period_transaction(client, personal_id)
    second = _create_current_period_transaction(client, personal_id)
    client.post(
        "/recurring/from-transaction",
        json={
            "transaction_id": first["transaction_id"],
            "label": "Abonnement Musique",
            "amount": -50.00,
            "periodicity": "mensuelle",
        },
    )
    response = client.post(
        "/recurring/from-transaction",
        json={
            "transaction_id": second["transaction_id"],
            "label": "Abonnement Musique",
            "amount": -50.00,
            "periodicity": "mensuelle",
        },
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_post_create_recurring_from_transaction_positive_transaction_amount_returns_422(client):
    personal_id, _ = _account_ids(client)
    transaction_response = client.post(
        "/transactions",
        json={
            "account_id": personal_id,
            "date": date.today().isoformat(),
            "amount": 1500.00,
            "label": "Salaire",
        },
    )
    transaction = transaction_response.json()["data"]
    response = client.post(
        "/recurring/from-transaction",
        json={
            "transaction_id": transaction["transaction_id"],
            "label": "Salaire",
            "amount": -1500.00,
            "periodicity": "mensuelle",
        },
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_get_recurring_transactions_filters_by_status(client):
    personal_id, _ = _account_ids(client)
    candidate = client.get(
        "/recurring/candidates", params={"account_id": personal_id}
    ).json()["data"][0]
    client.post(
        "/recurring/confirm",
        json={
            "account_id": personal_id,
            "signature": candidate["signature"],
            "label": candidate["label"],
            "amount": candidate["amount"],
            "periodicity": candidate["periodicity"],
        },
    )
    response = client.get(
        "/recurring", params={"account_id": personal_id, "status": "confirmed"}
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
