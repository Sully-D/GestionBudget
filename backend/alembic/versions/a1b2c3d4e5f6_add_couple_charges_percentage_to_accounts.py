"""add couple_charges_percentage to accounts

Revision ID: a1b2c3d4e5f6
Revises: 8e6fec6b91a4
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8e6fec6b91a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("couple_charges_percentage", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("couple_charges_percentage")
