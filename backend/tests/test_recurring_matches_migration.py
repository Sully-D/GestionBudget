import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_head_creates_recurring_matches_table_with_fks(tmp_path):
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
    assert "recurring_matches" in table_names

    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT * FROM recurring_matches")).fetchall()
    assert rows == []

    fks = inspector.get_foreign_keys("recurring_matches")
    assert len(fks) == 2
    referred_tables = {fk["referred_table"] for fk in fks}
    assert referred_tables == {"recurring_transactions", "transactions"}


def test_alembic_downgrade_drops_recurring_matches_table_only(tmp_path):
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

    downgrade_result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "7d2f4a1b9c3e"],
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
    assert "recurring_matches" not in table_names
    assert "planned_expenses" in table_names
    assert "recurring_transactions" in table_names
