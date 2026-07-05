from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.tags.schema import TagCreate, TagRead, TagUpdate
from app.tags.service import create_tag, delete_tag, list_tags, update_tag

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
def list_tags_endpoint(db: Session = Depends(get_db)):
    return {"data": [TagRead.model_validate(t) for t in list_tags(db)]}


@router.post("")
def post_tag(payload: TagCreate, db: Session = Depends(get_db)):
    tag = create_tag(payload, db)
    return {"data": TagRead.model_validate(tag)}


@router.put("/{tag_id}")
def put_tag(tag_id: int, payload: TagUpdate, db: Session = Depends(get_db)):
    tag = update_tag(tag_id, payload, db)
    return {"data": TagRead.model_validate(tag)}


@router.delete("/{tag_id}")
def delete_tag_endpoint(tag_id: int, db: Session = Depends(get_db)):
    delete_tag(tag_id, db)
    return {"data": None}
