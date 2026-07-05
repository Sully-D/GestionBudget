from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.tags.model import MAX_LEVEL, Rule, Tag
from app.tags.rule_engine.dispatcher import evaluate_rules_verbose
from app.tags.schema import RuleCreate, RuleUpdate, TagCreate, TagUpdate


def list_tags(db: Session) -> list[Tag]:
    return db.query(Tag).order_by(Tag.tag_id).all()


def get_tag(tag_id: int, db: Session) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} introuvable")
    return tag


def create_tag(payload: TagCreate, db: Session) -> Tag:
    if payload.parent_id is None:
        level = 1
    else:
        parent = db.get(Tag, payload.parent_id)
        if parent is None:
            raise HTTPException(
                status_code=422, detail=f"Tag parent {payload.parent_id} introuvable"
            )
        if parent.level >= MAX_LEVEL:
            raise HTTPException(
                status_code=422,
                detail=f"Profondeur maximale de {MAX_LEVEL} niveaux atteinte",
            )
        level = parent.level + 1
    tag = Tag(name=payload.name, parent_id=payload.parent_id, level=level)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def update_tag(tag_id: int, payload: TagUpdate, db: Session) -> Tag:
    tag = get_tag(tag_id, db)
    tag.name = payload.name
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(tag_id: int, db: Session) -> None:
    tag = get_tag(tag_id, db)
    has_children = db.query(Tag).filter(Tag.parent_id == tag_id).first() is not None
    if has_children:
        raise HTTPException(status_code=422, detail="Supprimez d'abord les tags enfants")
    db.delete(tag)
    db.commit()


def list_rules(db: Session) -> list[Rule]:
    return db.query(Rule).order_by(Rule.sort_order).all()


def get_rule(rule_id: int, db: Session) -> Rule:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Règle {rule_id} introuvable")
    return rule


def _validate_tag_exists(tag_id: int, db: Session) -> None:
    if db.get(Tag, tag_id) is None:
        raise HTTPException(status_code=422, detail=f"Tag {tag_id} introuvable")


def create_rule(payload: RuleCreate, db: Session) -> Rule:
    _validate_tag_exists(payload.tag_id, db)
    max_order = db.query(func.max(Rule.sort_order)).scalar()
    next_order = (max_order or 0) + 1
    rule = Rule(
        condition_type=payload.condition_type,
        condition_value=payload.condition_value,
        tag_id=payload.tag_id,
        sort_order=next_order,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(rule_id: int, payload: RuleUpdate, db: Session) -> Rule:
    rule = get_rule(rule_id, db)
    _validate_tag_exists(payload.tag_id, db)
    rule.condition_type = payload.condition_type
    rule.condition_value = payload.condition_value
    rule.tag_id = payload.tag_id
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(rule_id: int, db: Session) -> None:
    rule = get_rule(rule_id, db)
    db.delete(rule)
    db.commit()


def evaluate_transaction_tag(label: str, payee: str | None, db: Session) -> Rule | None:
    rules = list_rules(db)
    return evaluate_rules_verbose(rules, label, payee)


def reorder_rules(rule_ids: list[int], db: Session) -> list[Rule]:
    existing_ids = {r.rule_id for r in db.query(Rule.rule_id).all()}
    if set(rule_ids) != existing_ids or len(rule_ids) != len(existing_ids):
        raise HTTPException(
            status_code=422,
            detail="La liste doit contenir exactement l'ensemble des règles existantes, sans doublon.",
        )
    for position, rule_id in enumerate(rule_ids, start=1):
        db.query(Rule).filter(Rule.rule_id == rule_id).update({"sort_order": position})
    db.commit()
    return list_rules(db)
