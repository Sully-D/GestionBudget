import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_head_creates_tags_table_with_self_referencing_fk(tmp_path):
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
    assert "tags" in table_names

    with engine.connect() as conn:
        tags_rows = conn.execute(sa.text("SELECT * FROM tags")).fetchall()
    assert tags_rows == []

    fks = inspector.get_foreign_keys("tags")
    assert len(fks) == 1
    assert fks[0]["referred_table"] == "tags"
    assert fks[0]["constrained_columns"] == ["parent_id"]


def test_alembic_downgrade_drops_tags_table_only(tmp_path):
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

    # Cible explicitement la révision `add_transactions_table` plutôt que le
    # relatif `-1` : `-1` est relatif à la tête de chaîne courante, qui a
    # avancé depuis (migration `add_transaction_tags_table` ajoutée en
    # Story 2.2) ; un downgrade relatif n'annulerait alors que cette
    # dernière migration, pas celle de `tags` que ce test vise spécifiquement.
    downgrade_result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "61b1207be884"],
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
    assert "tags" not in table_names
    assert "accounts" in table_names
    assert "transactions" in table_names
