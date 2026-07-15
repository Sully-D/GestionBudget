"""add csv column mappings table

Revision ID: 8e6fec6b91a4
Revises: 9a1e5f6b2c8d
Create Date: 2026-07-15 11:33:19.073137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e6fec6b91a4'
down_revision: Union[str, Sequence[str], None] = '9a1e5f6b2c8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "csv_column_mappings",
        sa.Column("mapping_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("header_signature", sa.String(), nullable=False),
        sa.Column("date_column", sa.String(), nullable=False),
        sa.Column("montant_column", sa.String(), nullable=False),
        sa.Column("libelle_column", sa.String(), nullable=False),
        sa.Column("tiers_column", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("mapping_id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.UniqueConstraint(
            "account_id", "header_signature", name="uq_csv_column_mappings_account_signature"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("csv_column_mappings")
