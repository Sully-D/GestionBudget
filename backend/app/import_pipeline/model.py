from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CsvColumnMapping(Base):
    """Dernier mappage de colonnes CSV utilisé avec succès pour un couple
    (compte, signature d'en-têtes) -- une seule ligne par couple (upsert)."""

    __tablename__ = "csv_column_mappings"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "header_signature", name="uq_csv_column_mappings_account_signature"
        ),
    )

    mapping_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.account_id"), nullable=False
    )
    header_signature: Mapped[str] = mapped_column(String, nullable=False)
    date_column: Mapped[str] = mapped_column(String, nullable=False)
    montant_column: Mapped[str] = mapped_column(String, nullable=False)
    libelle_column: Mapped[str] = mapped_column(String, nullable=False)
    tiers_column: Mapped[str | None] = mapped_column(String, nullable=True)
