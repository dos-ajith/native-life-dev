from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import CommunityMessages
from app.models.community import Community
from app.models.community_member import CommunityMember, CommunityMemberStatus
from app.models.user import User
from app.repositories.community_member_repository import CommunityMemberRepository
from app.repositories.community_repository import CommunityRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.community_access import ensure_owner, lock_owned, lock_published
from app.services.notification_service import NotificationService

ENTITY_TYPE = "community"


class CommunityMembershipService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._communities = CommunityRepository(db)
        self._members = CommunityMemberRepository(db)
        self._users = UserRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)

    def join(self, community_id: UUID, actor: User) -> CommunityMember:
        community = lock_published(self._communities, community_id)
        existing = self._members.get(community.id, actor.id)
        if existing is not None:
            self._raise_for_existing(existing)
        if community.auto_approve_members:
            self._ensure_capacity(community)
            status = CommunityMemberStatus.ACTIVE
            community.members_count += 1
        else:
            status = CommunityMemberStatus.PENDING
        member = self._members.stage(
            CommunityMember(community_id=community.id, user_id=actor.id, status=status)
        )
        self._db.commit()
        if status == CommunityMemberStatus.ACTIVE:
            self._log(actor, ActivityAction.COMMUNITY_JOINED, community)
        else:
            self._log(actor, ActivityAction.COMMUNITY_JOIN_REQUESTED, community)
            self._notifications.notify_community_join_requested(
                community.owner_id, actor, community.id, community.name
            )
        return member

    def leave(self, community_id: UUID, actor: User) -> CommunityMemberStatus:
        community = lock_published(self._communities, community_id)
        member = self._members.get(community.id, actor.id)
        if member is None or member.status == CommunityMemberStatus.BLOCKED:
            raise NotFoundError(CommunityMessages.NOT_A_MEMBER)
        if community.owner_id == actor.id:
            raise BusinessRuleError(CommunityMessages.OWNER_CANNOT_LEAVE)
        previous = member.status
        self._remove(community, member)
        self._db.commit()
        action = (
            ActivityAction.COMMUNITY_LEFT
            if previous == CommunityMemberStatus.ACTIVE
            else ActivityAction.COMMUNITY_JOIN_REQUEST_CANCELLED
        )
        self._log(actor, action, community)
        return previous

    def list_members(
        self, community_id: UUID, actor: User, params: PaginationParams
    ) -> tuple[list[CommunityMember], int]:
        community = self._published(community_id)
        if not self._members.is_active_member(community.id, actor.id):
            raise AuthorizationError(CommunityMessages.NOT_A_MEMBER)
        return self._members.list_by_status(community.id, CommunityMemberStatus.ACTIVE, params)

    def list_requests(
        self, community_id: UUID, actor: User, params: PaginationParams
    ) -> tuple[list[CommunityMember], int]:
        community = self._published(community_id)
        ensure_owner(community, actor)
        return self._members.list_by_status(community.id, CommunityMemberStatus.PENDING, params)

    def list_blocked(
        self, community_id: UUID, actor: User, params: PaginationParams
    ) -> tuple[list[CommunityMember], int]:
        community = self._published(community_id)
        ensure_owner(community, actor)
        return self._members.list_by_status(community.id, CommunityMemberStatus.BLOCKED, params)

    def approve_request(self, community_id: UUID, user_id: UUID, actor: User) -> CommunityMember:
        community = lock_owned(self._communities, community_id, actor)
        member = self._pending_request(community, user_id)
        self._ensure_capacity(community)
        member.status = CommunityMemberStatus.ACTIVE
        community.members_count += 1
        self._db.commit()
        self._log(actor, ActivityAction.COMMUNITY_JOIN_APPROVED, community, user_id)
        self._notifications.notify_community_join_decided(
            user_id, actor, community.id, community.name, True
        )
        return member

    def reject_request(self, community_id: UUID, user_id: UUID, actor: User) -> None:
        community = lock_owned(self._communities, community_id, actor)
        member = self._pending_request(community, user_id)
        self._remove(community, member)
        self._db.commit()
        self._log(actor, ActivityAction.COMMUNITY_JOIN_REJECTED, community, user_id)
        self._notifications.notify_community_join_decided(
            user_id, actor, community.id, community.name, False
        )

    def remove_member(self, community_id: UUID, user_id: UUID, actor: User) -> None:
        community = lock_owned(self._communities, community_id, actor)
        self._ensure_not_owner(community, user_id)
        member = self._members.get(community.id, user_id)
        if member is None or member.status != CommunityMemberStatus.ACTIVE:
            raise NotFoundError(CommunityMessages.MEMBER_NOT_FOUND)
        self._remove(community, member)
        self._db.commit()
        self._log(actor, ActivityAction.COMMUNITY_MEMBER_REMOVED, community, user_id)

    def block_member(self, community_id: UUID, user_id: UUID, actor: User) -> None:
        community = lock_owned(self._communities, community_id, actor)
        self._ensure_not_owner(community, user_id)
        member = self._members.get(community.id, user_id)
        if member is None:
            if self._users.get_by_id(user_id) is None:
                raise NotFoundError(CommunityMessages.MEMBER_NOT_FOUND)
            self._members.stage(
                CommunityMember(
                    community_id=community.id,
                    user_id=user_id,
                    status=CommunityMemberStatus.BLOCKED,
                )
            )
        else:
            if member.status == CommunityMemberStatus.ACTIVE:
                community.members_count -= 1
            member.status = CommunityMemberStatus.BLOCKED
        self._db.commit()
        self._log(actor, ActivityAction.COMMUNITY_MEMBER_BLOCKED, community, user_id)

    def unblock_member(self, community_id: UUID, user_id: UUID, actor: User) -> None:
        community = lock_owned(self._communities, community_id, actor)
        member = self._members.get(community.id, user_id)
        if member is None or member.status != CommunityMemberStatus.BLOCKED:
            raise NotFoundError(CommunityMessages.NOT_BLOCKED)
        self._members.stage_delete(member)
        self._db.commit()
        self._log(actor, ActivityAction.COMMUNITY_MEMBER_UNBLOCKED, community, user_id)

    def _published(self, community_id: UUID) -> Community:
        community = self._communities.get_by_id(community_id)
        if community is None or not self._communities.is_published(community):
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        return community

    def _pending_request(self, community: Community, user_id: UUID) -> CommunityMember:
        member = self._members.get(community.id, user_id)
        if member is None or member.status != CommunityMemberStatus.PENDING:
            raise NotFoundError(CommunityMessages.REQUEST_NOT_FOUND)
        return member

    def _remove(self, community: Community, member: CommunityMember) -> None:
        if member.status == CommunityMemberStatus.ACTIVE:
            community.members_count -= 1
        self._members.stage_delete(member)

    @staticmethod
    def _ensure_capacity(community: Community) -> None:
        if community.max_members is not None and community.members_count >= community.max_members:
            raise BusinessRuleError(CommunityMessages.FULL)

    @staticmethod
    def _ensure_not_owner(community: Community, user_id: UUID) -> None:
        if community.owner_id == user_id:
            raise BusinessRuleError(CommunityMessages.CANNOT_MODERATE_OWNER)

    @staticmethod
    def _raise_for_existing(member: CommunityMember) -> None:
        if member.status == CommunityMemberStatus.BLOCKED:
            raise AuthorizationError(CommunityMessages.BLOCKED)
        if member.status == CommunityMemberStatus.ACTIVE:
            raise BusinessRuleError(CommunityMessages.ALREADY_MEMBER)
        raise BusinessRuleError(CommunityMessages.ALREADY_REQUESTED)

    def _log(
        self, actor: User, action: str, community: Community, target_user_id: UUID | None = None
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=community.id,
            metadata={"user_id": str(target_user_id)} if target_user_id is not None else None,
        )
