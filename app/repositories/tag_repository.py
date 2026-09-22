from collections import defaultdict
from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models.post_tag import post_tags
from app.models.tag import Tag


class TagRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_slugs(self, slugs: list[str]) -> list[Tag]:
        if not slugs:
            return []
        return list(self._db.scalars(select(Tag).where(Tag.slug.in_(slugs))))

    def add(self, tag: Tag) -> Tag:
        self._db.add(tag)
        self._db.commit()
        self._db.refresh(tag)
        return tag

    def list_by_post(self, post_id: UUID) -> list[Tag]:
        return self.list_by_posts([post_id]).get(post_id, [])

    def list_by_posts(self, post_ids: list[UUID]) -> dict[UUID, list[Tag]]:
        if not post_ids:
            return {}
        rows = self._db.execute(
            select(post_tags.c.post_id, Tag)
            .join(Tag, Tag.id == post_tags.c.tag_id)
            .where(post_tags.c.post_id.in_(post_ids))
            .order_by(Tag.name)
        ).all()
        grouped: dict[UUID, list[Tag]] = defaultdict(list)
        for post_id, tag in rows:
            grouped[post_id].append(tag)
        return grouped

    def replace_post_tags(self, post_id: UUID, tag_ids: list[UUID]) -> None:
        self._db.execute(delete(post_tags).where(post_tags.c.post_id == post_id))
        if tag_ids:
            self._db.execute(
                insert(post_tags),
                [{"post_id": post_id, "tag_id": tag_id} for tag_id in tag_ids],
            )
        self._db.commit()
