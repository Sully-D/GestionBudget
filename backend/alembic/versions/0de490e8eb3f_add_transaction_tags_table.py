"""add transaction_tags table

Revision ID: 0de490e8eb3f
Revises: 8c4771f6ec20
Create Date: 2026-07-03 06:41:37.690436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0de490e8eb3f'
down_revision: Union[str, Sequence[str], None] = '8c4771f6ec20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "transaction_tags",
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("transaction_id", "tag_id"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.transaction_id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.tag_id"]),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("transaction_tags")
