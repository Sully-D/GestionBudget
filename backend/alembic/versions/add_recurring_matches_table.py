"""add recurring matches table

Revision ID: 9a1e5f6b2c8d
Revises: 7d2f4a1b9c3e
Create Date: 2026-07-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1e5f6b2c8d'
down_revision: Union[str, Sequence[str], None] = '7d2f4a1b9c3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "recurring_matches",
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("recurring_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')", name="ck_recurring_matches_status"
        ),
        sa.PrimaryKeyConstraint("match_id"),
        sa.ForeignKeyConstraint(["recurring_id"], ["recurring_transactions.recurring_id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.transaction_id"]),
        sa.UniqueConstraint("transaction_id", name="uq_recurring_matches_transaction_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("recurring_matches")
