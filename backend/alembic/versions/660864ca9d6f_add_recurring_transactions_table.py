"""add recurring transactions table

Revision ID: 660864ca9d6f
Revises: 0c7cb82f61d9
Create Date: 2026-07-06 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '660864ca9d6f'
down_revision: Union[str, Sequence[str], None] = '0c7cb82f61d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "recurring_transactions",
        sa.Column("recurring_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=True),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("periodicity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("recurring_id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.tag_id"]),
        sa.CheckConstraint(
            "periodicity IN ('hebdomadaire', 'mensuelle', 'trimestrielle', 'annuelle')",
            name="ck_recurring_transactions_periodicity",
        ),
        sa.CheckConstraint(
            "status IN ('confirmed', 'rejected')",
            name="ck_recurring_transactions_status",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("recurring_transactions")
