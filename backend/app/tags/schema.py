from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1)
    parent_id: int | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed == "":
            raise ValueError("le nom du Tag ne peut pas être composé uniquement d'espaces")
        return trimmed


class TagUpdate(BaseModel):
    # Pas de `parent_id` : le renommage ne déplace jamais un tag dans l'arbre (AC #7).
    name: str = Field(..., min_length=1)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed == "":
            raise ValueError("le nom du Tag ne peut pas être composé uniquement d'espaces")
        return trimmed


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tag_id: int
    name: str
    parent_id: int | None
    level: int


class RuleCreate(BaseModel):
    condition_type: Literal["label_contains", "payee_exact"]
    condition_value: str = Field(..., min_length=1)
    tag_id: int

    @field_validator("condition_value")
    @classmethod
    def _condition_value_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed == "":
            raise ValueError("la valeur de la condition ne peut pas être composée uniquement d'espaces")
        return trimmed


class RuleUpdate(BaseModel):
    # Pas de `sort_order` ici : l'ordre ne change que via l'endpoint dédié PUT /rules/reorder.
    condition_type: Literal["label_contains", "payee_exact"]
    condition_value: str = Field(..., min_length=1)
    tag_id: int

    @field_validator("condition_value")
    @classmethod
    def _condition_value_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed == "":
            raise ValueError("la valeur de la condition ne peut pas être composée uniquement d'espaces")
        return trimmed


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rule_id: int
    condition_type: str
    condition_value: str
    tag_id: int
    sort_order: int
