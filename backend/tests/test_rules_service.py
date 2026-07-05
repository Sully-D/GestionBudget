import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.tags.model import Tag
from app.tags.schema import RuleCreate, RuleUpdate
from app.tags.service import (
    create_rule,
    delete_rule,
    get_rule,
    list_rules,
    reorder_rules,
    update_rule,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_rules_service.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    yield session
    session.close()


@pytest.fixture
def tag(db):
    t = Tag(name="Alimentation", parent_id=None, level=1)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def other_tag(db):
    t = Tag(name="Loisirs", parent_id=None, level=1)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_create_rule_label_contains(db, tag):
    rule = create_rule(
        RuleCreate(condition_type="label_contains", condition_value="Carrefour", tag_id=tag.tag_id),
        db,
    )
    assert rule.sort_order == 1
    assert rule.condition_type == "label_contains"


def test_create_rule_payee_exact(db, tag):
    rule = create_rule(
        RuleCreate(condition_type="payee_exact", condition_value="EDF", tag_id=tag.tag_id),
        db,
    )
    assert rule.condition_type == "payee_exact"


def test_create_rule_second_time_appends_sort_order(db, tag):
    create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db)
    second = create_rule(
        RuleCreate(condition_type="label_contains", condition_value="B", tag_id=tag.tag_id), db
    )
    assert second.sort_order == 2


def test_create_rule_with_nonexistent_tag_raises_422(db):
    with pytest.raises(HTTPException) as exc_info:
        create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=999), db)
    assert exc_info.value.status_code == 422


def test_update_rule_modifies_fields_without_touching_sort_order(db, tag, other_tag):
    rule = create_rule(
        RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db
    )
    original_sort_order = rule.sort_order
    updated = update_rule(
        rule.rule_id,
        RuleUpdate(condition_type="payee_exact", condition_value="B", tag_id=other_tag.tag_id),
        db,
    )
    assert updated.condition_type == "payee_exact"
    assert updated.condition_value == "B"
    assert updated.tag_id == other_tag.tag_id
    assert updated.sort_order == original_sort_order


def test_update_rule_raises_404_when_missing(db, tag):
    with pytest.raises(HTTPException) as exc_info:
        update_rule(
            999,
            RuleUpdate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id),
            db,
        )
    assert exc_info.value.status_code == 404


def test_update_rule_with_nonexistent_tag_raises_422(db, tag):
    rule = create_rule(
        RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db
    )
    with pytest.raises(HTTPException) as exc_info:
        update_rule(
            rule.rule_id,
            RuleUpdate(condition_type="label_contains", condition_value="A", tag_id=999),
            db,
        )
    assert exc_info.value.status_code == 422


def test_delete_rule_removes_it_and_does_not_renumber_remaining(db, tag):
    r1 = create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db)
    r2 = create_rule(RuleCreate(condition_type="label_contains", condition_value="B", tag_id=tag.tag_id), db)
    r3 = create_rule(RuleCreate(condition_type="label_contains", condition_value="C", tag_id=tag.tag_id), db)
    delete_rule(r2.rule_id, db)
    remaining = list_rules(db)
    assert [r.rule_id for r in remaining] == [r1.rule_id, r3.rule_id]
    assert [r.sort_order for r in remaining] == [1, 3]


def test_delete_rule_raises_404_when_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_rule(999, db)
    assert exc_info.value.status_code == 404


def test_get_rule_returns_existing_rule(db, tag):
    rule = create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db)
    found = get_rule(rule.rule_id, db)
    assert found.rule_id == rule.rule_id


def test_get_rule_raises_404_when_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        get_rule(999, db)
    assert exc_info.value.status_code == 404


def test_list_rules_sorted_by_sort_order_ascending(db, tag):
    r1 = create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db)
    r2 = create_rule(RuleCreate(condition_type="label_contains", condition_value="B", tag_id=tag.tag_id), db)
    reordered = reorder_rules([r2.rule_id, r1.rule_id], db)
    assert [r.rule_id for r in reordered] == [r2.rule_id, r1.rule_id]
    assert [r.sort_order for r in list_rules(db)] == [1, 2]


def test_reorder_rules_reassigns_sort_order_by_position(db, tag):
    r1 = create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db)
    r2 = create_rule(RuleCreate(condition_type="label_contains", condition_value="B", tag_id=tag.tag_id), db)
    r3 = create_rule(RuleCreate(condition_type="label_contains", condition_value="C", tag_id=tag.tag_id), db)
    reordered = reorder_rules([r3.rule_id, r1.rule_id, r2.rule_id], db)
    assert [(r.rule_id, r.sort_order) for r in reordered] == [
        (r3.rule_id, 1),
        (r1.rule_id, 2),
        (r2.rule_id, 3),
    ]


def test_reorder_rules_missing_id_raises_422(db, tag):
    r1 = create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db)
    create_rule(RuleCreate(condition_type="label_contains", condition_value="B", tag_id=tag.tag_id), db)
    with pytest.raises(HTTPException) as exc_info:
        reorder_rules([r1.rule_id], db)
    assert exc_info.value.status_code == 422


def test_reorder_rules_extra_id_raises_422(db, tag):
    r1 = create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db)
    with pytest.raises(HTTPException) as exc_info:
        reorder_rules([r1.rule_id, 999], db)
    assert exc_info.value.status_code == 422


def test_reorder_rules_duplicate_id_raises_422(db, tag):
    r1 = create_rule(RuleCreate(condition_type="label_contains", condition_value="A", tag_id=tag.tag_id), db)
    r2 = create_rule(RuleCreate(condition_type="label_contains", condition_value="B", tag_id=tag.tag_id), db)
    with pytest.raises(HTTPException) as exc_info:
        reorder_rules([r1.rule_id, r1.rule_id], db)
    assert exc_info.value.status_code == 422
