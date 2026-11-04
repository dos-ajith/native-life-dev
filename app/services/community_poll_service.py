import logging
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import CommunityMessages, PollMessages
from app.core.timezone import naive_app_now, to_naive_app_time
from app.models.community import Community
from app.models.community_poll import CommunityPoll, CommunityPollOption
from app.models.user import User
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.community_member_repository import CommunityMemberRepository
from app.repositories.community_poll_repository import CommunityPollRepository
from app.repositories.community_repository import CommunityRepository
from app.schemas.community_poll import CommunityPollCreate, CommunityPollRead
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService

logger = logging.getLogger("app.community_poll")


class CommunityPollService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._publisher = publisher or get_realtime_publisher()
        self._communities = CommunityRepository(db)
        self._members = CommunityMemberRepository(db)
        self._polls = CommunityPollRepository(db)
        self._activity_logs = ActivityLogService(db)

    def create(
        self, community_id: UUID, actor: User, payload: CommunityPollCreate
    ) -> CommunityPollRead:
        community = self._published_community(community_id)
        if community.owner_id != actor.id:
            raise AuthorizationError(PollMessages.POLL_OWNER_ONLY)
        ends_at = self._validated_end(payload)
        poll = self._polls.add(
            CommunityPoll(
                community_id=community.id,
                author_id=actor.id,
                question=payload.question,
                allows_multiple=payload.allows_multiple,
                show_results_before_vote=payload.show_results_before_vote,
                ends_at=ends_at,
                options=[
                    CommunityPollOption(text=text, position=position)
                    for position, text in enumerate(payload.options)
                ],
            )
        )
        self._log(actor, ActivityAction.POLL_CREATED, poll)
        self._announce(poll)
        return self._read_fresh(poll.id, actor)

    def list_polls(
        self, community_id: UUID, params: PaginationParams, viewer: User
    ) -> tuple[list[CommunityPollRead], int]:
        community = self._member_community(community_id, viewer)
        polls, total = self._polls.list_for_community(community.id, params)
        return self.reads_for(polls, viewer), total

    def get(self, community_id: UUID, poll_id: UUID, viewer: User) -> CommunityPollRead:
        community = self._member_community(community_id, viewer)
        return self._read(self._poll_in(community, poll_id), viewer)

    def vote(
        self, community_id: UUID, poll_id: UUID, actor: User, option_ids: Sequence[UUID]
    ) -> CommunityPollRead:
        community = self._member_community(community_id, actor)
        poll = self._open_poll_for_update(community, poll_id)
        if not set(option_ids) <= {option.id for option in poll.options}:
            raise BusinessRuleError(PollMessages.UNKNOWN_OPTION)
        if not poll.allows_multiple and len(option_ids) > 1:
            raise BusinessRuleError(PollMessages.SINGLE_CHOICE_ONLY)
        previous = set(self._polls.list_user_option_ids(actor.id, [poll.id]).get(poll.id, []))
        chosen = set(option_ids)
        self._polls.stage_vote_removals(poll.id, actor.id, sorted(previous - chosen))
        self._polls.stage_votes(poll.id, actor.id, sorted(chosen - previous))
        self._polls.commit()
        self._log(actor, ActivityAction.POLL_VOTED, poll)
        return self._read_fresh(poll.id, actor)

    def remove_vote(self, community_id: UUID, poll_id: UUID, actor: User) -> CommunityPollRead:
        community = self._member_community(community_id, actor)
        poll = self._open_poll_for_update(community, poll_id)
        previous = self._polls.list_user_option_ids(actor.id, [poll.id]).get(poll.id, [])
        if not previous:
            raise BusinessRuleError(PollMessages.NOT_VOTED)
        self._polls.stage_vote_removals(poll.id, actor.id, previous)
        self._polls.commit()
        self._log(actor, ActivityAction.POLL_VOTE_REMOVED, poll)
        return self._read_fresh(poll.id, actor)

    def reads_for(self, polls: Sequence[CommunityPoll], viewer: User) -> list[CommunityPollRead]:
        chosen = (
            self._polls.list_user_option_ids(viewer.id, [poll.id for poll in polls])
            if polls
            else {}
        )
        return [
            CommunityPollRead.from_poll(poll, chosen.get(poll.id, []), viewer.id) for poll in polls
        ]

    def reads_by_ids(self, poll_ids: Sequence[UUID], viewer: User) -> dict[UUID, CommunityPollRead]:
        if not poll_ids:
            return {}
        reads = self.reads_for(self._polls.list_by_ids(poll_ids), viewer)
        return {read.id: read for read in reads}

    @staticmethod
    def _validated_end(payload: CommunityPollCreate) -> datetime | None:
        if payload.ends_at is None:
            return None
        ends_at = to_naive_app_time(payload.ends_at)
        if ends_at <= naive_app_now():
            raise BusinessRuleError(PollMessages.ENDS_AT_IN_PAST)
        return ends_at

    def _published_community(self, community_id: UUID) -> Community:
        community = self._communities.get_by_id(community_id)
        if community is None or not self._communities.is_published(community):
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        return community

    def _member_community(self, community_id: UUID, actor: User) -> Community:
        community = self._published_community(community_id)
        if not self._members.is_active_member(community.id, actor.id):
            raise AuthorizationError(PollMessages.MEMBERS_ONLY)
        return community

    def _poll_in(self, community: Community, poll_id: UUID) -> CommunityPoll:
        poll = self._polls.get_by_id(poll_id)
        if poll is None or poll.community_id != community.id:
            raise NotFoundError(PollMessages.NOT_FOUND)
        return poll

    def _open_poll_for_update(self, community: Community, poll_id: UUID) -> CommunityPoll:
        poll = self._polls.get_for_update(poll_id)
        if poll is None or poll.community_id != community.id:
            raise NotFoundError(PollMessages.NOT_FOUND)
        if poll.is_closed:
            raise BusinessRuleError(PollMessages.CLOSED)
        return poll

    def _read(self, poll: CommunityPoll, viewer: User) -> CommunityPollRead:
        return self.reads_for([poll], viewer)[0]

    def _read_fresh(self, poll_id: UUID, viewer: User) -> CommunityPollRead:
        poll = self._polls.get_by_id(poll_id)
        if poll is None:
            raise NotFoundError(PollMessages.NOT_FOUND)
        return self._read(poll, viewer)

    def _announce(self, poll: CommunityPoll) -> None:
        try:
            event_data = {
                "community_id": str(poll.community_id),
                "poll_id": str(poll.id),
                "author_id": str(poll.author_id),
            }
            for user_id in self._members.list_active_user_ids(poll.community_id):
                if self._publisher.has_connections(user_id):
                    self._publisher.publish_to_user(
                        user_id,
                        RealtimeEvent(
                            type=RealtimeEventType.COMMUNITY_POLL_CREATED, data=event_data
                        ),
                    )
        except Exception:
            logger.exception("Failed to announce poll %s", poll.id)

    def _log(self, actor: User, action: str, poll: CommunityPoll) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type="community_poll",
            entity_id=poll.id,
            metadata={"community_id": str(poll.community_id)},
        )
