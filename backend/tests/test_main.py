from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, get_db
from main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}


def test_no_auth_middleware_registered():
    assert app.user_middleware == []


def test_accounts_endpoint_reachable_without_credentials(tmp_path):
    # Comportement réel garanti (pas de session, cookie ou header requis) —
    # complète le test ci-dessus qui ne vérifie qu'un détail d'implémentation.
    db_path = tmp_path / "test_main_no_auth.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/accounts")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
