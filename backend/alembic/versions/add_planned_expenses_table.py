"""add planned expenses table

Revision ID: 7d2f4a1b9c3e
Revises: 660864ca9d6f
Create Date: 2026-07-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d2f4a1b9c3e'
down_revision: Union[str, Sequence[str], None] = '660864ca9d6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "planned_expenses",
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.String(), nullable=True),
        sa.Column("period_index", sa.Integer(), nullable=True),
        sa.Column("total_periods", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("expense_id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.tag_id"]),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("planned_expenses")
