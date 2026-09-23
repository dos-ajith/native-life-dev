from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError
from app.core.messages import TagMessages
from app.models.tag import Tag
from app.models.user import User
from app.repositories.tag_repository import TagRepository
from app.services.activity_log_service import ActivityLogService
from app.utils.slug import slugify


class TagService:
    def __init__(self, db: Session) -> None:
        self._tags = TagRepository(db)
        self._activity_logs = ActivityLogService(db)

    def resolve(self, names: list[str], actor: User) -> list[Tag]:
        slug_to_name: dict[str, str] = {}
        for name in names:
            stripped = name.strip()
            slug = slugify(stripped)
            if not slug:
                raise BusinessRuleError(TagMessages.INVALID_NAME)
            slug_to_name.setdefault(slug, stripped)
        if not slug_to_name:
            return []

        existing = {tag.slug: tag for tag in self._tags.get_by_slugs(list(slug_to_name))}
        resolved: list[Tag] = []
        for slug, name in slug_to_name.items():
            tag = existing.get(slug)
            if tag is None:
                tag = self._tags.add(Tag(name=name, slug=slug))
                self._activity_logs.log(
                    actor=actor,
                    action=ActivityAction.TAG_CREATED,
                    entity_type="tag",
                    entity_id=tag.id,
                    metadata={"slug": tag.slug},
                )
            resolved.append(tag)
        return resolved

    def set_post_tags(self, post_id: UUID, names: list[str], actor: User) -> list[Tag]:
        tags = self.resolve(names, actor)
        self._tags.replace_post_tags(post_id, [tag.id for tag in tags])
        return tags

    def list_for_post(self, post_id: UUID) -> list[Tag]:
        return self._tags.list_by_post(post_id)

    def list_for_posts(self, post_ids: list[UUID]) -> dict[UUID, list[Tag]]:
        return self._tags.list_by_posts(post_ids)

    def search(self, query: str, limit: int) -> list[Tag]:
        return self._tags.search_by_name(query, limit)
