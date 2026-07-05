import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.tags.model import Tag
from app.tags.schema import TagCreate, TagUpdate
from app.tags.service import create_tag, delete_tag, get_tag, list_tags, update_tag


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_tags_service.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    yield session
    session.close()


def test_create_tag_without_parent_is_level_1(db):
    tag = create_tag(TagCreate(name="Alimentation"), db)
    assert tag.level == 1
    assert tag.parent_id is None


def test_create_tag_with_level_1_parent_is_level_2(db):
    parent = create_tag(TagCreate(name="Alimentation"), db)
    child = create_tag(TagCreate(name="Courses", parent_id=parent.tag_id), db)
    assert child.level == 2
    assert child.parent_id == parent.tag_id


def test_create_tag_with_level_2_parent_is_level_3(db):
    l1 = create_tag(TagCreate(name="Alimentation"), db)
    l2 = create_tag(TagCreate(name="Courses", parent_id=l1.tag_id), db)
    l3 = create_tag(TagCreate(name="Bio", parent_id=l2.tag_id), db)
    assert l3.level == 3
    assert l3.parent_id == l2.tag_id


def test_create_tag_with_level_3_parent_raises_422(db):
    l1 = create_tag(TagCreate(name="Alimentation"), db)
    l2 = create_tag(TagCreate(name="Courses", parent_id=l1.tag_id), db)
    l3 = create_tag(TagCreate(name="Bio", parent_id=l2.tag_id), db)
    with pytest.raises(HTTPException) as exc_info:
        create_tag(TagCreate(name="Niveau 4", parent_id=l3.tag_id), db)
    assert exc_info.value.status_code == 422


def test_create_tag_with_nonexistent_parent_raises_422(db):
    with pytest.raises(HTTPException) as exc_info:
        create_tag(TagCreate(name="Orphelin", parent_id=999), db)
    assert exc_info.value.status_code == 422


def test_create_tag_without_parent_always_produces_level_1_regardless_of_db_state(db):
    # Preuve structurelle de l'AC #4 : aucun moyen de produire un niveau 2/3
    # sans fournir un `parent_id` valide, quel que soit l'état de la base.
    create_tag(TagCreate(name="Existant"), db)
    tag = create_tag(TagCreate(name="Un autre racine"), db)
    assert tag.level == 1


def test_update_tag_renames_and_preserves_parent_and_level(db):
    parent = create_tag(TagCreate(name="Alimentation"), db)
    child = create_tag(TagCreate(name="Courses", parent_id=parent.tag_id), db)
    updated = update_tag(child.tag_id, TagUpdate(name="Courses alimentaires"), db)
    assert updated.name == "Courses alimentaires"
    assert updated.parent_id == parent.tag_id
    assert updated.level == 2


def test_update_tag_raises_404_when_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        update_tag(999, TagUpdate(name="Test"), db)
    assert exc_info.value.status_code == 404


def test_delete_tag_without_children_removes_it(db):
    tag = create_tag(TagCreate(name="Sport"), db)
    tag_id = tag.tag_id
    delete_tag(tag_id, db)
    assert [t.tag_id for t in list_tags(db)] == []


def test_delete_tag_with_children_raises_422_and_keeps_tags(db):
    parent = create_tag(TagCreate(name="Alimentation"), db)
    child = create_tag(TagCreate(name="Courses", parent_id=parent.tag_id), db)
    with pytest.raises(HTTPException) as exc_info:
        delete_tag(parent.tag_id, db)
    assert exc_info.value.status_code == 422
    assert "enfants" in exc_info.value.detail
    remaining_ids = {t.tag_id for t in list_tags(db)}
    assert parent.tag_id in remaining_ids
    assert child.tag_id in remaining_ids


def test_delete_tag_raises_404_when_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_tag(999, db)
    assert exc_info.value.status_code == 404


def test_get_tag_returns_existing_tag(db):
    tag = create_tag(TagCreate(name="Loisirs"), db)
    found = get_tag(tag.tag_id, db)
    assert found.tag_id == tag.tag_id


def test_get_tag_raises_404_when_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        get_tag(999, db)
    assert exc_info.value.status_code == 404


def test_list_tags_empty_on_fresh_db(db):
    assert list_tags(db) == []


def test_list_tags_reflects_creations(db):
    create_tag(TagCreate(name="A"), db)
    create_tag(TagCreate(name="B"), db)
    assert [t.name for t in list_tags(db)] == ["A", "B"]
