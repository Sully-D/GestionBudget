import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_head_creates_transactions_table_with_fk(tmp_path):
    db_path = tmp_path / "test_migration.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(db_path)

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db_path}")
    inspector = sa.inspect(engine)
    table_names = inspector.get_table_names()
    assert "accounts" in table_names
    assert "transactions" in table_names

    with engine.connect() as conn:
        accounts_count = conn.execute(
            sa.text("SELECT COUNT(*) FROM accounts")
        ).scalar()
        transactions_rows = conn.execute(
            sa.text("SELECT * FROM transactions")
        ).fetchall()
    assert accounts_count == 3
    assert transactions_rows == []

    fks = inspector.get_foreign_keys("transactions")
    assert len(fks) == 1
    assert fks[0]["referred_table"] == "accounts"
    assert fks[0]["constrained_columns"] == ["account_id"]

    # Convention DB : jamais de float pour les montants (ARCHITECTURE-SPINE.md,
    # ligne 182) — vérifie le type SQL réel, pas seulement le comportement.
    columns_by_name = {col["name"]: col for col in inspector.get_columns("transactions")}
    assert isinstance(columns_by_name["amount"]["type"], sa.Numeric)


def test_alembic_downgrade_drops_transactions_table_only(tmp_path):
    db_path = tmp_path / "test_migration_downgrade.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(db_path)

    upgrade_result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert upgrade_result.returncode == 0, upgrade_result.stderr

    # Cible explicitement la révision `add_accounts_table` plutôt que le
    # relatif `-1` : `-1` est relatif à la tête de chaîne courante, qui a
    # avancé depuis (migration `add_tags_table` ajoutée en Story 2.1) ; un
    # downgrade relatif n'annulerait alors que cette dernière migration,
    # pas celle de `transactions` que ce test vise spécifiquement.
    downgrade_result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "e2af66951283"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert downgrade_result.returncode == 0, downgrade_result.stderr

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        table_names = sa.inspect(conn).get_table_names()
    assert "transactions" not in table_names
    assert "accounts" in table_names
