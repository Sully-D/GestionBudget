"""add accounts table

Revision ID: e2af66951283
Revises: 9dd12ce4bbba
Create Date: 2026-07-01 16:57:10.830356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2af66951283'
down_revision: Union[str, Sequence[str], None] = '9dd12ce4bbba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


accounts_table = sa.table(
    "accounts",
    sa.column("account_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("is_common", sa.Boolean),
    sa.column("start_day", sa.Integer),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_common", sa.Boolean(), nullable=False),
        sa.Column("start_day", sa.Integer(), nullable=False),
        sa.Column("reference_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint("start_day >= 1 AND start_day <= 28", name="ck_accounts_start_day_range"),
    )
    op.bulk_insert(
        accounts_table,
        [
            {"name": "Personnel-Lui", "is_common": False, "start_day": 1},
            {"name": "Personnel-Elle", "is_common": False, "start_day": 1},
            {"name": "Commun", "is_common": True, "start_day": 1},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("accounts")
