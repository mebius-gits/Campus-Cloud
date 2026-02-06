"""Item CRUD 操作"""

import uuid

from sqlmodel import Session

from app.models import Item, ItemCreate


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    """建立新 Item"""
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


__all__ = ["create_item"]
