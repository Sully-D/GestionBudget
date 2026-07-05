import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_alembic(*args, env):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_alembic_upgrade_head_adds_fitid_column(tmp_path):
    db_path = tmp_path / "test_import_migration.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(db_path)

    result = _run_alembic("upgrade", "head", env=env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db_path}")
    inspector = sa.inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("transactions")}
    assert "fitid" in columns


def test_manual_transaction_with_null_fitid_succeeds(tmp_path):
    db_path = tmp_path / "test_import_migration_null.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(db_path)

    result = _run_alembic("upgrade", "head", env=env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO accounts (name, is_common, start_day) "
                "VALUES ('Compte', 0, 1)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO transactions (account_id, date, amount, label, fitid) "
                "VALUES (1, '2026-07-01', -10.00, 'Manuelle', NULL)"
            )
        )

    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT label, fitid FROM transactions WHERE account_id = 1")
        ).one()
    assert row.label == "Manuelle"
    assert row.fitid is None


def test_duplicate_fitid_same_account_raises_integrity_error(tmp_path):
    db_path = tmp_path / "test_import_migration_dup.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(db_path)

    result = _run_alembic("upgrade", "head", env=env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO accounts (name, is_common, start_day) "
                "VALUES ('Compte', 0, 1)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO transactions (account_id, date, amount, label, fitid) "
                "VALUES (1, '2026-07-01', -10.00, 'Import 1', 'FIT1')"
            )
        )

    with pytest.raises(sa.exc.IntegrityError) as exc_info:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO transactions (account_id, date, amount, label, fitid) "
                    "VALUES (1, '2026-07-02', -20.00, 'Import 2', 'FIT1')"
                )
            )
    # Vérifie que c'est bien la contrainte d'unicité (account_id, fitid) qui a
    # échoué, pas une autre IntegrityError sans rapport (ex. NOT NULL/type).
    assert "UNIQUE constraint failed: transactions.account_id, transactions.fitid" in str(
        exc_info.value
    )


def test_two_null_fitid_same_account_do_not_conflict(tmp_path):
    db_path = tmp_path / "test_import_migration_two_null.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(db_path)

    result = _run_alembic("upgrade", "head", env=env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO accounts (name, is_common, start_day) "
                "VALUES ('Compte', 0, 1)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO transactions (account_id, date, amount, label, fitid) "
                "VALUES (1, '2026-07-01', -10.00, 'Manuelle 1', NULL)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO transactions (account_id, date, amount, label, fitid) "
                "VALUES (1, '2026-07-02', -20.00, 'Manuelle 2', NULL)"
            )
        )

    with engine.connect() as conn:
        count = conn.execute(sa.text("SELECT COUNT(*) FROM transactions")).scalar()
    assert count == 2


def test_alembic_downgrade_to_6b2faef3e64f_drops_fitid_column(tmp_path):
    db_path = tmp_path / "test_import_migration_downgrade.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(db_path)

    upgrade_result = _run_alembic("upgrade", "head", env=env)
    assert upgrade_result.returncode == 0, upgrade_result.stderr

    # Cible explicitement la révision précédente connue plutôt que le relatif
    # `-1` : cette migration est en tête de chaîne, même précédent que
    # `test_rules_migration.py`.
    downgrade_result = _run_alembic("downgrade", "6b2faef3e64f", env=env)
    assert downgrade_result.returncode == 0, downgrade_result.stderr

    engine = sa.create_engine(f"sqlite:///{db_path}")
    inspector = sa.inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("transactions")}
    assert "fitid" not in columns
