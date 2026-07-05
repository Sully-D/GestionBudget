"""add budget targets table

Revision ID: 0c7cb82f61d9
Revises: f3a7c1d9b2e4
Create Date: 2026-07-05 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c7cb82f61d9'
down_revision: Union[str, Sequence[str], None] = 'f3a7c1d9b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "budget_targets",
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.PrimaryKeyConstraint("target_id"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.tag_id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("budget_targets")
