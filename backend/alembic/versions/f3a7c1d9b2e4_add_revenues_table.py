"""add revenues table

Revision ID: f3a7c1d9b2e4
Revises: 5c9ddfffa47c
Create Date: 2026-07-04 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7c1d9b2e4'
down_revision: Union[str, Sequence[str], None] = '5c9ddfffa47c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "revenues",
        sa.Column("revenue_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("revenue_id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.CheckConstraint("kind IN ('salaire', 'ponctuel')", name="ck_revenues_kind"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("revenues")
