from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Doit rester en phase avec la contrainte DB figée dans la migration
# 8c4771f6ec20 ("level >= 1 AND level <= 3") — modifier cette constante ne
# changera pas rétroactivement une migration déjà appliquée.
MAX_LEVEL = 3


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        CheckConstraint(
            f"level >= 1 AND level <= {MAX_LEVEL}", name="ck_tags_level_range"
        ),
    )

    tag_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tags.tag_id"), nullable=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (
        CheckConstraint(
            "condition_type IN ('label_contains', 'payee_exact')",
            name="ck_rules_condition_type",
        ),
    )

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    condition_type: Mapped[str] = mapped_column(String, nullable=False)
    condition_value: Mapped[str] = mapped_column(String, nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.tag_id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
