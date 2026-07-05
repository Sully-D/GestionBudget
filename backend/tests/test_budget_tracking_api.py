from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.model import BudgetTarget, Revenue
from app.core.db import Base, get_db
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag
from main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_budget_tracking_api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    today = date.today()
    period_start = date(today.year, today.month, 1)

    with testing_session_local() as session:
        personal = Account(name="Personnel-Lui", is_common=False, start_day=1)
        common = Account(name="Commun", is_common=True, start_day=1)
        session.add_all([personal, common])
        session.commit()
        session.refresh(personal)
        session.refresh(common)

        tag = Tag(name="Alimentation", parent_id=None, level=1)
        session.add(tag)
        session.commit()
        session.refresh(tag)

        session.add(Revenue(account_id=personal.account_id, period_start=None, kind="salaire", amount=Decimal("1000.00")))
        session.add(BudgetTarget(account_id=personal.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")))
        session.commit()

        tx = Transaction(
            account_id=personal.account_id,
            date=today,
            amount=Decimal("-150.00"),
            label="Courses",
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)
        session.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag.tag_id))
        session.commit()

        state = {
            "personal_id": personal.account_id,
            "common_id": common.account_id,
            "tag_id": tag.tag_id,
            "period_start": period_start,
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


def test_get_tag_tracking_returns_data_envelope(client):
    test_client, state = client
    response = test_client.get(
        "/tag-tracking",
        params={"account_id": state["personal_id"], "period_start": state["period_start"].isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    data = body["data"]
    row = next(r for r in data if r["tag_id"] == state["tag_id"])
    assert row["spent"] == 150.0
    assert isinstance(row["spent"], float)
    assert row["target_amount"] == 200.0
    assert row["gap"] == 50.0


def test_get_tag_tracking_on_common_account_returns_422(client):
    test_client, state = client
    response = test_client.get(
        "/tag-tracking",
        params={"account_id": state["common_id"], "period_start": state["period_start"].isoformat()},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_get_tag_tracking_unknown_account_returns_404(client):
    test_client, state = client
    response = test_client.get(
        "/tag-tracking",
        params={"account_id": 999, "period_start": state["period_start"].isoformat()},
    )
    assert response.status_code == 404
