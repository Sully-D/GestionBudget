import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.core.db import Base, get_db
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_transactions_api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session_local() as session:
        session.add_all(
            [
                Account(name="Personnel-Lui", is_common=False, start_day=1),
                Account(name="Personnel-Elle", is_common=False, start_day=1),
                Account(name="Commun", is_common=True, start_day=1),
            ]
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


@pytest.fixture
def account_id(client):
    accounts = client.get("/accounts").json()["data"]
    return accounts[0]["account_id"]


def test_post_transaction_valid_persists_and_updates_balance(client, account_id):
    response = client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-07-02",
            "amount": -42.90,
            "label": "Carrefour",
            "payee": "Carrefour",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["label"] == "Carrefour"
    assert data["amount"] == -42.9

    account_response = client.get(f"/accounts/{account_id}")
    assert account_response.json()["data"]["balance"] == -42.9


def test_post_transaction_missing_label_returns_422(client, account_id):
    response = client.post(
        "/transactions",
        json={"account_id": account_id, "date": "2026-07-02", "amount": -10, "label": ""},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_post_transaction_whitespace_only_label_returns_422(client, account_id):
    response = client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-07-02",
            "amount": -10,
            "label": "   ",
        },
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_post_transaction_missing_amount_returns_422(client, account_id):
    response = client.post(
        "/transactions",
        json={"account_id": account_id, "date": "2026-07-02", "label": "Test"},
    )
    assert response.status_code == 422


def test_post_transaction_missing_account_id_returns_422(client):
    response = client.post(
        "/transactions",
        json={"date": "2026-07-02", "amount": -10, "label": "Test"},
    )
    assert response.status_code == 422


def test_post_transaction_nonexistent_account_returns_404(client):
    response = client.post(
        "/transactions",
        json={"account_id": 999, "date": "2026-07-02", "amount": -10, "label": "Test"},
    )
    assert response.status_code == 404


def test_get_transactions_without_data_returns_empty_list(client, account_id):
    response = client.get(f"/transactions?account_id={account_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["transactions"] == []
    assert data["period_start"] is not None
    assert data["period_end"] is not None


def test_get_transactions_sorted_by_date_desc(client, account_id):
    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-07-01",
            "amount": -10,
            "label": "Première",
        },
    )
    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-07-05",
            "amount": -20,
            "label": "Plus récente",
        },
    )
    response = client.get(f"/transactions?account_id={account_id}")
    transactions = response.json()["data"]["transactions"]
    assert [t["label"] for t in transactions] == ["Plus récente", "Première"]


def test_get_transactions_filters_by_past_period(client, account_id):
    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-05-15",
            "amount": -10,
            "label": "Période passée",
        },
    )
    client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-07-02",
            "amount": -20,
            "label": "Période courante",
        },
    )
    response = client.get(
        f"/transactions?account_id={account_id}&reference_date=2026-05-15"
    )
    transactions = response.json()["data"]["transactions"]
    assert len(transactions) == 1
    assert transactions[0]["label"] == "Période passée"


def test_get_transactions_without_account_id_returns_422(client):
    response = client.get("/transactions")
    assert response.status_code == 422


def test_get_transactions_without_account_id_but_html_accept_serves_frontend(client):
    # Collision de route : le chemin frontend `/transactions` (liste) est identique
    # au chemin API GET `/transactions`. Une navigation directe/rafraîchissement
    # du navigateur (Accept: text/html, pas d'account_id) doit servir la SPA,
    # pas l'erreur 422 destinée aux appels API.
    response = client.get("/transactions", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_get_transactions_without_account_id_low_priority_html_accept_returns_422(client):
    # Un client API qui liste "text/html" en dernier recours (q=0.1) ne doit
    # pas recevoir la SPA à la place de l'erreur 422 attendue : seul le type
    # média prioritaire (premier de la liste) doit déclencher le fallback HTML.
    response = client.get(
        "/transactions", headers={"accept": "application/json, text/html;q=0.1"}
    )
    assert response.status_code == 422


def test_get_transactions_html_accept_missing_frontend_index_returns_404(client, monkeypatch):
    import app.transactions.router as transactions_router

    monkeypatch.setattr(
        transactions_router, "FRONTEND_INDEX", transactions_router.Path("does/not/exist.html")
    )
    response = client.get("/transactions", headers={"accept": "text/html"})
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


@pytest.fixture
def transaction_id(client, account_id):
    response = client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-07-02",
            "amount": -10.00,
            "label": "Original",
            "payee": "Original Payee",
        },
    )
    return response.json()["data"]["transaction_id"]


def test_put_transaction_valid_updates_fields_and_balance(client, account_id, transaction_id):
    response = client.put(
        f"/transactions/{transaction_id}",
        json={
            "date": "2026-07-05",
            "amount": -25.50,
            "label": "Modifié",
            "payee": "Nouveau Tiers",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["date"] == "2026-07-05"
    assert data["amount"] == -25.5
    assert data["label"] == "Modifié"
    assert data["payee"] == "Nouveau Tiers"
    assert data["account_id"] == account_id

    account_response = client.get(f"/accounts/{account_id}")
    assert account_response.json()["data"]["balance"] == -25.5


def test_put_transaction_blank_label_returns_422(client, transaction_id):
    response = client.put(
        f"/transactions/{transaction_id}",
        json={"date": "2026-07-05", "amount": -10, "label": "   "},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_put_transaction_nonexistent_returns_404(client):
    response = client.put(
        "/transactions/999",
        json={"date": "2026-07-05", "amount": -10, "label": "Test"},
    )
    assert response.status_code == 404


def test_get_transaction_by_id_returns_transaction(client, transaction_id):
    response = client.get(f"/transactions/{transaction_id}")
    assert response.status_code == 200
    assert response.json()["data"]["transaction_id"] == transaction_id


def test_get_transaction_by_id_nonexistent_returns_404(client):
    response = client.get("/transactions/999")
    assert response.status_code == 404


def test_delete_transaction_removes_it_and_updates_balance(
    client, account_id, transaction_id
):
    response = client.delete(f"/transactions/{transaction_id}")
    assert response.status_code == 200
    assert response.json()["data"] is None

    list_response = client.get(f"/transactions?account_id={account_id}")
    transaction_ids = [
        t["transaction_id"] for t in list_response.json()["data"]["transactions"]
    ]
    assert transaction_id not in transaction_ids

    account_response = client.get(f"/accounts/{account_id}")
    assert account_response.json()["data"]["balance"] == 0.0


def test_delete_transaction_nonexistent_returns_404(client):
    response = client.delete("/transactions/999")
    assert response.status_code == 404


@pytest.fixture
def tag_id(client):
    response = client.post("/tags", json={"name": "Alimentation"})
    return response.json()["data"]["tag_id"]


@pytest.fixture
def other_tag_id(client):
    response = client.post("/tags", json={"name": "Loisirs"})
    return response.json()["data"]["tag_id"]


def test_post_transaction_tag_valid_associates_tag(client, transaction_id, tag_id):
    response = client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": tag_id})
    assert response.status_code == 200
    tags = response.json()["data"]["tags"]
    assert [t["tag_id"] for t in tags] == [tag_id]


def test_post_transaction_tag_second_tag_keeps_both(
    client, transaction_id, tag_id, other_tag_id
):
    client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": tag_id})
    response = client.post(
        f"/transactions/{transaction_id}/tags", json={"tag_id": other_tag_id}
    )
    assert response.status_code == 200
    tag_ids = {t["tag_id"] for t in response.json()["data"]["tags"]}
    assert tag_ids == {tag_id, other_tag_id}


def test_post_transaction_tag_duplicate_is_idempotent(client, transaction_id, tag_id):
    client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": tag_id})
    response = client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": tag_id})
    assert response.status_code == 200
    tags = response.json()["data"]["tags"]
    assert [t["tag_id"] for t in tags] == [tag_id]


def test_post_transaction_tag_nonexistent_tag_returns_422(client, transaction_id):
    response = client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": 999})
    assert response.status_code == 422


def test_post_transaction_tag_nonexistent_transaction_returns_404(client, tag_id):
    response = client.post("/transactions/999/tags", json={"tag_id": tag_id})
    assert response.status_code == 404


def test_delete_transaction_tag_removes_only_targeted_tag(
    client, transaction_id, tag_id, other_tag_id
):
    client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": tag_id})
    client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": other_tag_id})

    response = client.delete(f"/transactions/{transaction_id}/tags/{tag_id}")
    assert response.status_code == 200
    assert response.json()["data"] is None

    get_response = client.get(f"/transactions/{transaction_id}")
    remaining = get_response.json()["data"]["tags"]
    assert [t["tag_id"] for t in remaining] == [other_tag_id]


def test_delete_transaction_tag_absent_association_is_noop(client, transaction_id, tag_id):
    response = client.delete(f"/transactions/{transaction_id}/tags/{tag_id}")
    assert response.status_code == 200
    assert response.json()["data"] is None


def test_delete_transaction_tag_nonexistent_transaction_returns_404(client, tag_id):
    response = client.delete(f"/transactions/999/tags/{tag_id}")
    assert response.status_code == 404


def test_get_transactions_untagged_returns_empty_tags(client, account_id, transaction_id):
    response = client.get(f"/transactions?account_id={account_id}")
    transactions = response.json()["data"]["transactions"]
    assert transactions[0]["tags"] == []


def test_get_transaction_by_id_reflects_associated_tags(client, transaction_id, tag_id):
    client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": tag_id})
    response = client.get(f"/transactions/{transaction_id}")
    tags = response.json()["data"]["tags"]
    assert [t["tag_id"] for t in tags] == [tag_id]
    assert tags[0]["name"] == "Alimentation"


def test_get_transactions_nouvelle_html_accept_still_serves_frontend(client):
    # Non-régression : l'ajout des routes `/transactions/{transaction_id:int}`
    # ne doit pas casser l'accès direct/rafraîchissement de la page de création
    # `/transactions/nouvelle` (2 segments, même arité que la route par id).
    response = client.get("/transactions/nouvelle", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_get_tag_usage_count_unused_tag_returns_zero(client, tag_id):
    response = client.get(f"/transactions/tags/{tag_id}/count")
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 0


def test_get_tag_usage_count_after_one_association_returns_one(
    client, transaction_id, tag_id
):
    client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": tag_id})
    response = client.get(f"/transactions/tags/{tag_id}/count")
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 1


def test_get_tag_usage_count_after_two_associations_returns_two(
    client, account_id, transaction_id, tag_id
):
    other_transaction = client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "date": "2026-07-02",
            "amount": -5.00,
            "label": "Autre",
            "payee": "Autre Payee",
        },
    ).json()["data"]["transaction_id"]

    client.post(f"/transactions/{transaction_id}/tags", json={"tag_id": tag_id})
    client.post(f"/transactions/{other_transaction}/tags", json={"tag_id": tag_id})

    response = client.get(f"/transactions/tags/{tag_id}/count")
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 2


def test_get_tag_usage_count_nonexistent_tag_returns_zero(client):
    response = client.get("/transactions/tags/999/count")
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 0
