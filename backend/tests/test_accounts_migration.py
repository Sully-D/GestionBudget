import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_head_creates_accounts_table_with_three_rows(tmp_path):
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
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT name, is_common, start_day FROM accounts ORDER BY account_id"
            )
        ).fetchall()

    assert len(rows) == 3
    assert rows[0] == ("Personnel-Lui", 0, 1)
    assert rows[1] == ("Personnel-Elle", 0, 1)
    assert rows[2] == ("Commun", 1, 1)

    # Convention DB : jamais de float pour les montants (ARCHITECTURE-SPINE.md,
    # ligne 182) — vérifie le type SQL réel, pas seulement le comportement.
    inspector = sa.inspect(engine)
    columns_by_name = {col["name"]: col for col in inspector.get_columns("accounts")}
    assert isinstance(columns_by_name["reference_balance"]["type"], sa.Numeric)


def test_alembic_downgrade_drops_accounts_table(tmp_path):
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
        [sys.executable, "-m", "alembic", "downgrade", "9dd12ce4bbba"],
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
    assert "accounts" not in table_names
