from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import CommunityMessages
from app.core.permissions import RoleSlug
from app.core.storage import delete_media_file, save_community_image
from app.core.timezone import app_now
from app.models.community import MAX_COMMUNITY_RESUBMISSIONS, Community, CommunityStatus
from app.models.community_member import CommunityMember, CommunityMemberStatus
from app.models.user import User
from app.models.user_native_place import NativePlaceSlot
from app.repositories.community_member_repository import CommunityMemberRepository
from app.repositories.community_repository import CommunityRepository, PlaceIds
from app.repositories.community_unread_repository import CommunityUnreadRepository
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.account_role import AccountRoleVerificationStatus
from app.schemas.community import (
    CommunityCreate,
    CommunityRead,
    CommunityUpdate,
    NativePlaceMatch,
    RecommendedCommunityRead,
)
from app.schemas.pagination import PaginationParams
from app.services.account_role_status_service import AccountRoleStatusService
from app.services.activity_log_service import ActivityLogService
from app.services.community_access import ensure_owner
from app.services.notification_service import NotificationService
from app.services.user_native_place_service import UserNativePlaceService

ENTITY_TYPE = "community"
CLEARABLE_FIELDS = frozenset({"max_members", "description"})
COMMUNITY_CREATOR_STATUSES = frozenset(
    {AccountRoleVerificationStatus.VERIFIED, AccountRoleVerificationStatus.PENDING}
)
MATCH_BY_LEVEL = (NativePlaceMatch.VILLAGE, NativePlaceMatch.TALUK, NativePlaceMatch.DISTRICT)


class CommunityService:
    def __init__(self, db: Session) -> None:
        self._communities = CommunityRepository(db)
        self._members = CommunityMemberRepository(db)
        self._account_roles = AccountRoleStatusService(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)
        self._unread = CommunityUnreadRepository(db)
        self._native_places = UserNativePlaceService(db)
        self._native_place_rows = UserNativePlaceRepository(db)

    def create(
        self, payload: CommunityCreate, actor: User, image: UploadFile | None, upload_dir: str
    ) -> Community:
        self._ensure_community_creator(actor)
        if self._communities.owner_has_pending(actor.id):
            raise BusinessRuleError(CommunityMessages.PENDING_EXISTS)
        village_id = self._native_places.primary_village_id(actor)
        if village_id is None:
            raise BusinessRuleError(CommunityMessages.NATIVE_PLACE_REQUIRED)
        self._ensure_name_available(payload.name)
        image_url = save_community_image(image, upload_dir) if image is not None else None
        try:
            community = self._add_pending(payload, actor, image_url, village_id)
        except Exception:
            self._discard_image(image_url, upload_dir)
            raise
        self._log(actor, ActivityAction.COMMUNITY_CREATED, community)
        self._notifications.notify_community_submitted(actor, community.id, community.name)
        return community

    def _add_pending(
        self, payload: CommunityCreate, actor: User, image_url: str | None, village_id: UUID
    ) -> Community:
        return self._communities.add(
            Community(
                owner_id=actor.id,
                name=payload.name,
                description=payload.description,
                image_url=image_url,
                village_id=village_id,
                auto_approve_members=payload.auto_approve_members,
                max_members=payload.max_members,
                status=CommunityStatus.PENDING,
            )
        )

    def update(
        self,
        community_id: UUID,
        payload: CommunityUpdate,
        actor: User,
        image: UploadFile | None,
        upload_dir: str,
    ) -> Community:
        community = self._communities.get_for_update(community_id)
        if community is None:
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        ensure_owner(community, actor)
        if community.status == CommunityStatus.BLOCKED:
            raise BusinessRuleError(CommunityMessages.EDIT_BLOCKED)
        changes = payload.model_dump(exclude_unset=True)
        new_name = changes.get("name")
        if new_name is not None and new_name.lower() != community.name.lower():
            self._ensure_name_available(new_name, community.id)
        new_max = changes.get("max_members")
        if new_max is not None and new_max < community.members_count:
            raise BusinessRuleError(CommunityMessages.MAX_MEMBERS_BELOW_COUNT)
        for field, value in changes.items():
            if value is not None or field in CLEARABLE_FIELDS:
                setattr(community, field, value)
        resubmitted = community.status == CommunityStatus.REJECTED
        if resubmitted:
            community.resubmission_count += 1
            community.status = CommunityStatus.PENDING
            community.reviewed_by = None
            community.reviewed_at = None
            community.review_note = None
        updated_fields = list(changes)
        previous_image_url = community.image_url
        new_image_url = save_community_image(image, upload_dir) if image is not None else None
        if new_image_url is not None:
            community.image_url = new_image_url
            updated_fields.append("image_url")
        try:
            saved = self._communities.save(community)
        except Exception:
            self._discard_image(new_image_url, upload_dir)
            raise
        if new_image_url is not None and previous_image_url is not None:
            self._discard_image(previous_image_url, upload_dir)
        self._log(
            actor, ActivityAction.COMMUNITY_UPDATED, saved, {"updated_fields": updated_fields}
        )
        if resubmitted:
            self._log(actor, ActivityAction.COMMUNITY_RESUBMITTED, saved)
            self._notifications.notify_community_submitted(actor, saved.id, saved.name)
        return saved

    def get_for_viewer(self, community_id: UUID, viewer: User) -> CommunityRead:
        community = self._communities.get_by_id(community_id)
        if community is None or not (
            self._communities.is_published(community) or community.owner_id == viewer.id
        ):
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        return self._to_reads([community], viewer)[0]

    def search(
        self, query: str | None, params: PaginationParams, viewer: User
    ) -> tuple[list[CommunityRead], int]:
        communities, total = self._communities.search_published(query, params)
        return self._to_reads(communities, viewer), total

    def list_recommended(
        self, params: PaginationParams, viewer: User
    ) -> tuple[list[RecommendedCommunityRead], int]:
        places = self._recommendation_places(viewer)
        rows, total = self._communities.list_recommended(viewer.id, places, params)
        reads = self._to_reads([community for community, _ in rows], viewer)
        return [
            RecommendedCommunityRead.from_read(read, MATCH_BY_LEVEL[rank // len(places)])
            for read, (_, rank) in zip(reads, rows, strict=True)
        ], total

    def list_mine(self, params: PaginationParams, viewer: User) -> tuple[list[CommunityRead], int]:
        communities, total = self._communities.list_for_user(viewer.id, params)
        return self._to_reads(communities, viewer), total

    def list_pending(
        self, params: PaginationParams, viewer: User
    ) -> tuple[list[CommunityRead], int]:
        communities, total = self._communities.list_pending(params)
        return self._to_reads(communities, viewer), total

    def approve(self, community_id: UUID, admin: User) -> Community:
        community = self._pending_for_review(community_id)
        self._ensure_owner_role_verified(community.owner_id)
        self._mark_reviewed(community, admin, CommunityStatus.PUBLISHED, None)
        self._members.stage(
            CommunityMember(
                community_id=community.id,
                user_id=community.owner_id,
                status=CommunityMemberStatus.ACTIVE,
            )
        )
        community.members_count = 1
        saved = self._communities.save(community)
        self._log(admin, ActivityAction.COMMUNITY_APPROVED, saved)
        self._notifications.notify_community_reviewed(
            saved.owner_id, admin, saved.id, saved.name, None
        )
        return saved

    def reject(self, community_id: UUID, admin: User, review_note: str) -> Community:
        community = self._pending_for_review(community_id)
        self._ensure_owner_role_verified(community.owner_id)
        exhausted = community.resubmission_count >= MAX_COMMUNITY_RESUBMISSIONS
        status = CommunityStatus.BLOCKED if exhausted else CommunityStatus.REJECTED
        return self._reject_pending(community, admin, review_note, status)

    def reject_pending_of_owner(self, owner_id: UUID, admin: User, review_note: str) -> None:
        for community_id in self._communities.list_pending_ids_by_owner(owner_id):
            community = self._pending_for_review(community_id)
            self._reject_pending(community, admin, review_note, CommunityStatus.REJECTED)

    def _reject_pending(
        self, community: Community, admin: User, review_note: str, status: CommunityStatus
    ) -> Community:
        self._mark_reviewed(community, admin, status, review_note)
        saved = self._communities.save(community)
        self._log(admin, ActivityAction.COMMUNITY_REJECTED, saved)
        self._notifications.notify_community_reviewed(
            saved.owner_id, admin, saved.id, saved.name, review_note
        )
        return saved

    @staticmethod
    def _discard_image(image_url: str | None, upload_dir: str) -> None:
        if image_url is not None:
            delete_media_file(image_url, upload_dir)

    def _pending_for_review(self, community_id: UUID) -> Community:
        community = self._communities.get_for_update(community_id)
        if community is None:
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        if community.status != CommunityStatus.PENDING:
            raise BusinessRuleError(CommunityMessages.NOT_PENDING)
        return community

    @staticmethod
    def _mark_reviewed(
        community: Community, reviewer: User, status: CommunityStatus, review_note: str | None
    ) -> None:
        community.status = status
        community.reviewed_by = reviewer.id
        community.reviewed_at = app_now()
        community.review_note = review_note

    def _ensure_owner_role_verified(self, owner_id: UUID) -> None:
        state = self._account_roles.state_for(owner_id)
        is_verified = (
            state is not None
            and state.role.slug == RoleSlug.CLUB_COMMUNITY
            and state.verification_status == AccountRoleVerificationStatus.VERIFIED
        )
        if not is_verified:
            raise BusinessRuleError(CommunityMessages.OWNER_ROLE_NOT_APPROVED)

    def _ensure_community_creator(self, actor: User) -> None:
        state = self._account_roles.state_for(actor.id)
        can_create = (
            state is not None
            and state.role.slug == RoleSlug.CLUB_COMMUNITY
            and state.verification_status in COMMUNITY_CREATOR_STATUSES
        )
        if not can_create:
            raise AuthorizationError(CommunityMessages.ROLE_NOT_VERIFIED)

    def _recommendation_places(self, viewer: User) -> list[PlaceIds]:
        places = sorted(
            self._native_place_rows.list_hierarchy(viewer.id),
            key=lambda item: item.slot != NativePlaceSlot.PRIMARY,
        )
        return [PlaceIds(item.village_id, item.taluk_id, item.district_id) for item in places]

    def _ensure_name_available(self, name: str, exclude_id: UUID | None = None) -> None:
        if self._communities.exists_with_name(name, exclude_id):
            raise BusinessRuleError(CommunityMessages.DUPLICATE_NAME)

    def _to_reads(self, communities: list[Community], viewer: User) -> list[CommunityRead]:
        statuses = (
            self._members.status_by_community(viewer.id, [item.id for item in communities])
            if communities
            else {}
        )
        member_of = [
            community_id
            for community_id, status in statuses.items()
            if status == CommunityMemberStatus.ACTIVE
        ]
        unread = self._unread.counts_for(viewer.id, member_of) if member_of else {}
        return [
            CommunityRead.from_community(
                item, viewer.id, statuses.get(item.id), unread.get(item.id, 0)
            )
            for item in communities
        ]

    def _log(
        self,
        actor: User,
        action: str,
        community: Community,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=community.id,
            metadata=metadata,
        )
