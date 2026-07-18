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
    db_path = tmp_path / "test_transactions_search_api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session_local() as session:
        account = Account(name="Personnel-Lui", is_common=False, start_day=1)
        session.add(account)
        session.commit()
        session.refresh(account)

        alimentation = Tag(name="Alimentation", parent_id=None, level=1)
        loisirs = Tag(name="Loisirs", parent_id=None, level=1)
        session.add_all([alimentation, loisirs])
        session.commit()
        session.refresh(alimentation)
        session.refresh(loisirs)

        t1 = Transaction(
            account_id=account.account_id,
            date=date(2026, 1, 5),
            amount=Decimal("-45.00"),
            label="Carrefour Marché",
            payee="Carrefour",
        )
        t2 = Transaction(
            account_id=account.account_id,
            date=date(2026, 2, 10),
            amount=Decimal("-25.00"),
            label="Cinéma Pathé",
            payee="Pathé",
        )
        t3 = Transaction(
            account_id=account.account_id,
            date=date(2026, 3, 15),
            amount=Decimal("-100.00"),
            label="Loyer",
            payee="Agence",
        )
        t4 = Transaction(
            account_id=account.account_id,
            date=date(2026, 3, 20),
            amount=Decimal("50.00"),
            label="Remboursement",
            payee="Ami",
        )
        t5 = Transaction(
            account_id=account.account_id,
            date=date(2026, 4, 1),
            amount=Decimal("-10.00"),
            label="Réduction 50%",
            payee="Boutique 50%",
        )
        t6 = Transaction(
            account_id=account.account_id,
            date=date(2026, 4, 2),
            amount=Decimal("-20.00"),
            label="Frais_fixe",
            payee="Service_X",
        )
        t7 = Transaction(
            account_id=account.account_id,
            date=date(2026, 4, 3),
            amount=Decimal("-5.00"),
            label="Bonus 50X",
            payee="Prime",
        )
        t8 = Transaction(
            account_id=account.account_id,
            date=date(2026, 4, 4),
            amount=Decimal("-6.00"),
            label="Autre frais",
            payee="ServiceZX",
        )
        session.add_all([t1, t2, t3, t4, t5, t6, t7, t8])
        session.commit()
        for t in (t1, t2, t3, t4, t5, t6, t7, t8):
            session.refresh(t)

        session.add_all(
            [
                TransactionTag(transaction_id=t1.transaction_id, tag_id=alimentation.tag_id),
                TransactionTag(transaction_id=t2.transaction_id, tag_id=loisirs.tag_id),
                TransactionTag(transaction_id=t4.transaction_id, tag_id=alimentation.tag_id),
                TransactionTag(transaction_id=t4.transaction_id, tag_id=loisirs.tag_id),
            ]
        )
        session.commit()

        state = {
            "account_id": account.account_id,
            "alimentation_id": alimentation.tag_id,
            "loisirs_id": loisirs.tag_id,
            "t1": t1.transaction_id,
            "t2": t2.transaction_id,
            "t3": t3.transaction_id,
            "t4": t4.transaction_id,
            "t5": t5.transaction_id,
            "t6": t6.transaction_id,
            "t7": t7.transaction_id,
            "t8": t8.transaction_id,
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


def _ids(response) -> set[int]:
    return {t["transaction_id"] for t in response.json()["data"]["transactions"]}


def test_no_filter_returns_unchanged_period_behavior(client):
    test_client, state = client
    response = test_client.get(f"/transactions?account_id={state['account_id']}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["filtered"] is False
    assert data["period_start"] is not None
    assert data["period_end"] is not None


def test_label_filter_is_case_insensitive_contains(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&label=carr"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["filtered"] is True
    assert data["period_start"] is None
    assert _ids(response) == {state["t1"]}


def test_payee_filter_is_case_insensitive_contains(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&payee=path"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t2"]}


def test_amount_exact_filter(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&amount=-45.00"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t1"]}


def test_amount_range_filter_is_inclusive(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&amount_min=-100&amount_max=-40"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t1"], state["t3"]}


def test_date_exact_filter(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&date_exact=2026-01-05"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t1"]}


def test_date_range_filter_is_inclusive(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}"
        "&date_from=2026-02-01&date_to=2026-03-16"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t2"], state["t3"]}


def test_multiple_tags_are_combined_with_or(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}"
        f"&tag_id={state['alimentation_id']}&tag_id={state['loisirs_id']}"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t1"], state["t2"], state["t4"]}


def test_different_filter_categories_are_combined_with_and(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}"
        f"&tag_id={state['alimentation_id']}&tag_id={state['loisirs_id']}&amount_min=0"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t4"]}


def test_no_match_returns_empty_list(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&label=zzzznotfound"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["filtered"] is True
    assert data["transactions"] == []


def test_nonexistent_tag_returns_empty_list_not_error(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&tag_id=9999"
    )
    assert response.status_code == 200
    assert response.json()["data"]["transactions"] == []


def test_percent_in_label_is_literal_not_wildcard(client):
    test_client, state = client
    # Sans échappement, "%" est un joker SQL LIKE ("50%" -> "contient '50'
    # suivi de n'importe quoi") et matcherait aussi t7 ("Bonus 50X").
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&label=50%25"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t5"]}


def test_underscore_in_payee_is_literal_not_wildcard(client):
    test_client, state = client
    # Sans échappement, "_" est un joker SQL LIKE (un caractère quelconque) et
    # matcherait aussi t8 ("ServiceZX").
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&payee=Service_X"
    )
    assert response.status_code == 200
    assert _ids(response) == {state["t6"]}


def test_whitespace_only_label_is_treated_as_no_filter(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&label=%20"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["filtered"] is False
    assert data["period_start"] is not None


def test_inconsistent_amount_range_returns_422(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&amount_min=50&amount_max=20"
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_inconsistent_date_range_returns_422(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}"
        "&date_from=2026-03-20&date_to=2026-01-01"
    )
    assert response.status_code == 422


def test_amount_exact_combined_with_range_returns_422(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}&amount=10&amount_min=5"
    )
    assert response.status_code == 422


def test_date_exact_combined_with_range_returns_422(client):
    test_client, state = client
    response = test_client.get(
        f"/transactions?account_id={state['account_id']}"
        "&date_exact=2026-01-05&date_from=2026-01-01"
    )
    assert response.status_code == 422
