"""add tags table

Revision ID: 8c4771f6ec20
Revises: 61b1207be884
Create Date: 2026-07-02 18:23:30.557638

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c4771f6ec20'
down_revision: Union[str, Sequence[str], None] = '61b1207be884'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tags",
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("tag_id"),
        sa.ForeignKeyConstraint(["parent_id"], ["tags.tag_id"]),
        # Le "3" ci-dessous doit rester en phase avec MAX_LEVEL (app/tags/model.py) —
        # une migration appliquée est figée, modifier MAX_LEVEL ne changera pas cette
        # contrainte DB rétroactivement ; une migration de suivi serait nécessaire.
        sa.CheckConstraint("level >= 1 AND level <= 3", name="ck_tags_level_range"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tags")
