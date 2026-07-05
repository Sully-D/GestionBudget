from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.tags.schema import RuleCreate, RuleRead, RuleUpdate
from app.tags.service import (
    create_rule,
    delete_rule,
    evaluate_transaction_tag,
    list_rules,
    reorder_rules,
    update_rule,
)

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleReorderPayload(BaseModel):
    rule_ids: list[int]


class RuleEvaluateRequest(BaseModel):
    label: str
    payee: str | None = None


@router.get("")
def list_rules_endpoint(db: Session = Depends(get_db)):
    return {"data": [RuleRead.model_validate(r) for r in list_rules(db)]}


@router.post("/evaluate")
def post_rules_evaluate(payload: RuleEvaluateRequest, db: Session = Depends(get_db)):
    rule = evaluate_transaction_tag(payload.label, payload.payee, db)
    return {
        "data": {
            "tag_id": rule.tag_id if rule else None,
            "condition_type": rule.condition_type if rule else None,
            "condition_value": rule.condition_value if rule else None,
        }
    }


@router.post("")
def post_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    rule = create_rule(payload, db)
    return {"data": RuleRead.model_validate(rule)}


@router.put("/reorder")
def put_rules_reorder(payload: RuleReorderPayload, db: Session = Depends(get_db)):
    rules = reorder_rules(payload.rule_ids, db)
    return {"data": [RuleRead.model_validate(r) for r in rules]}


@router.put("/{rule_id:int}")
def put_rule(rule_id: int, payload: RuleUpdate, db: Session = Depends(get_db)):
    rule = update_rule(rule_id, payload, db)
    return {"data": RuleRead.model_validate(rule)}


@router.delete("/{rule_id:int}")
def delete_rule_endpoint(rule_id: int, db: Session = Depends(get_db)):
    delete_rule(rule_id, db)
    return {"data": None}
