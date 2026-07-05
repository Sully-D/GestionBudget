"""add rules table

Revision ID: 6b2faef3e64f
Revises: 0de490e8eb3f
Create Date: 2026-07-03 07:22:51.071565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b2faef3e64f'
down_revision: Union[str, Sequence[str], None] = '0de490e8eb3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rules",
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("condition_type", sa.String(), nullable=False),
        sa.Column("condition_value", sa.String(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "condition_type IN ('label_contains', 'payee_exact')",
            name="ck_rules_condition_type",
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.tag_id"]),
        sa.PrimaryKeyConstraint("rule_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("rules")
