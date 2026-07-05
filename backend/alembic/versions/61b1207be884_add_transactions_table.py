"""add transactions table

Revision ID: 61b1207be884
Revises: e2af66951283
Create Date: 2026-07-02 09:40:47.154746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61b1207be884'
down_revision: Union[str, Sequence[str], None] = 'e2af66951283'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("payee", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("transaction_id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("transactions")
