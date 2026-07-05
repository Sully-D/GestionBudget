import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_head_creates_revenues_table_with_fk(tmp_path):
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
    assert "revenues" in table_names

    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT * FROM revenues")).fetchall()
    assert rows == []

    fks = inspector.get_foreign_keys("revenues")
    assert len(fks) == 1
    assert fks[0]["referred_table"] == "accounts"
    assert fks[0]["constrained_columns"] == ["account_id"]


def test_alembic_downgrade_drops_revenues_table_only(tmp_path):
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

    # Cible explicitement la révision précédente (`5c9ddfffa47c`) plutôt que
    # le relatif `-1` : même précédent que `test_rules_migration.py`.
    downgrade_result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "5c9ddfffa47c"],
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
    assert "revenues" not in table_names
    assert "accounts" in table_names
    assert "transactions" in table_names
