"""add fitid to transactions

Revision ID: 5c9ddfffa47c
Revises: 6b2faef3e64f
Create Date: 2026-07-03 19:28:17.711360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c9ddfffa47c'
down_revision: Union[str, Sequence[str], None] = '6b2faef3e64f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("fitid", sa.String(), nullable=True))
        batch_op.create_index(
            "ix_transactions_account_fitid", ["account_id", "fitid"], unique=True
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_index("ix_transactions_account_fitid")
        batch_op.drop_column("fitid")
