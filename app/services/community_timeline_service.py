import base64
import binascii
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import CommunityMessages, CommunityTimelineMessages
from app.models.user import User
from app.repositories.community_member_repository import CommunityMemberRepository
from app.repositories.community_message_repository import CommunityMessageRepository
from app.repositories.community_poll_repository import CommunityPollRepository
from app.repositories.community_repository import CommunityRepository
from app.repositories.community_timeline_repository import (
    CommunityTimelineRepository,
    TimelineEntry,
)
from app.repositories.post_repository import PostRepository, PostVisibilityScope
from app.schemas.community_timeline import (
    CommunityTimelineRead,
    TimelineItemRead,
    TimelineItemType,
    TimelineMessageItem,
    TimelineMessageRead,
    TimelinePollItem,
    TimelinePostItem,
    TimelinePostRead,
)
from app.services.community_poll_service import CommunityPollService
from app.services.post_service import PostService

CURSOR_SEPARATOR = "|"


def encode_cursor(entry: TimelineEntry) -> str:
    raw = f"{entry.sort_at.isoformat()}{CURSOR_SEPARATOR}{entry.id}{CURSOR_SEPARATOR}{entry.type}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> TimelineEntry:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        sort_at, entry_id, entry_type = raw.split(CURSOR_SEPARATOR)
        return TimelineEntry(
            id=UUID(entry_id),
            sort_at=datetime.fromisoformat(sort_at),
            type=TimelineItemType(entry_type),
        )
    except (binascii.Error, ValueError, UnicodeDecodeError) as error:
        raise BusinessRuleError(CommunityTimelineMessages.INVALID_CURSOR) from error


class CommunityTimelineService:
    def __init__(self, db: Session) -> None:
        self._communities = CommunityRepository(db)
        self._members = CommunityMemberRepository(db)
        self._messages = CommunityMessageRepository(db)
        self._posts = PostRepository(db)
        self._timeline = CommunityTimelineRepository(db)
        self._polls = CommunityPollRepository(db)
        self._poll_reads = CommunityPollService(db)
        self._post_details = PostService(db)

    def page(
        self, community_id: UUID, actor: User, before: str | None, limit: int
    ) -> CommunityTimelineRead:
        self._ensure_member(community_id, actor)
        cursor = decode_cursor(before) if before is not None else None
        scope = PostVisibilityScope(
            owner_id=actor.id, viewer_is_adult=actor.is_adult is True, member_id=actor.id
        )
        entries = self._timeline.page(
            [
                self._messages.timeline_entries(community_id),
                self._posts.timeline_entries(community_id, scope),
                self._polls.timeline_entries(community_id),
            ],
            cursor,
            limit + 1,
        )
        has_more = len(entries) > limit
        page_entries = entries[:limit]
        return CommunityTimelineRead(
            items=self._to_items(page_entries, actor),
            has_more=has_more,
            next_before=encode_cursor(page_entries[-1]) if has_more else None,
        )

    def _to_items(self, entries: list[TimelineEntry], actor: User) -> list[TimelineItemRead]:
        message_ids = [item.id for item in entries if item.type == TimelineItemType.MESSAGE]
        post_ids = [item.id for item in entries if item.type == TimelineItemType.POST]
        poll_ids = [item.id for item in entries if item.type == TimelineItemType.POLL]
        messages = {item.id: item for item in self._messages.list_by_ids(message_ids)}
        posts = self._post_details.details_by_ids(post_ids, actor)
        polls = self._poll_reads.reads_by_ids(poll_ids, actor)
        items: list[TimelineItemRead] = []
        for entry in entries:
            if entry.type == TimelineItemType.MESSAGE and entry.id in messages:
                items.append(
                    TimelineMessageItem(
                        message=TimelineMessageRead.from_message(messages[entry.id])
                    )
                )
            elif entry.type == TimelineItemType.POST and entry.id in posts:
                items.append(TimelinePostItem(post=TimelinePostRead.from_detail(posts[entry.id])))
            elif entry.type == TimelineItemType.POLL and entry.id in polls:
                items.append(TimelinePollItem(poll=polls[entry.id]))
        return items

    def _ensure_member(self, community_id: UUID, actor: User) -> None:
        community = self._communities.get_by_id(community_id)
        if community is None or not self._communities.is_published(community):
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        if not self._members.is_active_member(community.id, actor.id):
            raise AuthorizationError(CommunityMessages.NOT_A_MEMBER)
