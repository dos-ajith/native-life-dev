from collections.abc import Sequence
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Select, Table, Uuid, and_, exists, func, literal, select, update
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.orm import QueryableAttribute, Session

from app.models.deal import Deal, DealStatus
from app.models.deal_invitation import DealInvitation, DealInvitationStatus
from app.models.deal_native import DealNative
from app.models.user import User, UserStatus
from app.models.user_has_role import UserRoleAssignment
from app.models.user_native_place import NativePlaceSlot, UserNativePlace
from app.schemas.pagination import PaginationParams

_invitations = cast(Table, DealInvitation.__table__)


def _eligible_users(
    deal_id: UUID | QueryableAttribute[UUID],
    creator_id: UUID | QueryableAttribute[UUID],
    role_ids: Sequence[UUID],
) -> Select[UUID, UUID]:
    return (
        select(User.id.label("user_id"), UserRoleAssignment.role_id.label("role_id"))
        .join(UserRoleAssignment, UserRoleAssignment.user_id == User.id)
        .join(
            UserNativePlace,
            and_(
                UserNativePlace.user_id == User.id,
                UserNativePlace.slot == NativePlaceSlot.PRIMARY,
            ),
        )
        .join(DealNative, DealNative.village_id == UserNativePlace.village_id)
        .where(
            DealNative.deal_id == deal_id,
            UserRoleAssignment.role_id.in_(role_ids),
            UserRoleAssignment.verified_at.is_not(None),
            User.deleted_at.is_(None),
            User.status == UserStatus.ACTIVE,
            User.id != creator_id,
        )
    )


class DealInvitationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def invite_eligible(
        self, deal_id: UUID, creator_id: UUID, role_ids: Sequence[UUID]
    ) -> list[UUID]:
        eligible = (
            _eligible_users(deal_id, creator_id, role_ids)
            .ext(distinct_on(User.id))
            .order_by(User.id, UserRoleAssignment.role_id)
            .subquery()
        )
        statement = (
            insert(_invitations)
            .from_select(
                ["id", "deal_id", "user_id", "role_id", "status"],
                select(
                    func.gen_random_uuid(),
                    literal(deal_id, Uuid()),
                    eligible.c.user_id,
                    eligible.c.role_id,
                    literal(DealInvitationStatus.INVITED, _invitations.c.status.type),
                ),
            )
            .on_conflict_do_nothing(index_elements=["deal_id", "user_id"])
            .returning(_invitations.c.user_id)
        )
        return list(self._db.execute(statement).scalars())

    def is_eligible(
        self, deal_id: UUID, creator_id: UUID, user_id: UUID, role_ids: Sequence[UUID]
    ) -> bool:
        candidates = _eligible_users(deal_id, creator_id, role_ids).where(User.id == user_id)
        return bool(self._db.scalar(select(exists(candidates))))

    def get_for_user(self, deal_id: UUID, user_id: UUID) -> DealInvitation | None:
        return self._db.scalar(
            select(DealInvitation).where(
                DealInvitation.deal_id == deal_id, DealInvitation.user_id == user_id
            )
        )

    def accepted_user_id(self, deal_id: UUID) -> UUID | None:
        return self._db.scalar(
            select(DealInvitation.user_id).where(
                DealInvitation.deal_id == deal_id,
                DealInvitation.status == DealInvitationStatus.ACCEPTED,
            )
        )

    def list_unnotified(self, deal_id: UUID) -> list[DealInvitation]:
        return list(
            self._db.scalars(
                select(DealInvitation)
                .where(
                    DealInvitation.deal_id == deal_id,
                    DealInvitation.status == DealInvitationStatus.INVITED,
                    DealInvitation.notified_at.is_(None),
                )
                .order_by(DealInvitation.created_at, DealInvitation.id)
            )
        )

    def claim_for_notification(self, invitation_id: UUID, now: datetime) -> bool:
        result = self._db.execute(
            update(DealInvitation)
            .where(DealInvitation.id == invitation_id, DealInvitation.notified_at.is_(None))
            .values(notified_at=now)
            .returning(DealInvitation.id)
            .execution_options(synchronize_session=False)
        )
        self._db.commit()
        return result.first() is not None

    def list_open_for_user(
        self, user_id: UUID, role_ids: Sequence[UUID], now: datetime, params: PaginationParams
    ) -> tuple[list[DealInvitation], int]:
        conditions = [
            DealInvitation.user_id == user_id,
            DealInvitation.status == DealInvitationStatus.INVITED,
            Deal.status == DealStatus.PENDING_ACCEPTANCE,
            Deal.deleted_at.is_(None),
            Deal.acceptance_deadline > now,
            exists(_eligible_users(Deal.id, Deal.created_by, role_ids).where(User.id == user_id)),
        ]
        base = select(DealInvitation).join(Deal, Deal.id == DealInvitation.deal_id)
        total = (
            self._db.scalar(select(func.count()).select_from(base.where(*conditions).subquery()))
            or 0
        )
        offset = (params.page - 1) * params.page_size
        invitations = self._db.scalars(
            base.where(*conditions)
            .order_by(DealInvitation.created_at.desc(), DealInvitation.id)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(invitations), total

    def accept(self, deal_id: UUID, user_id: UUID, now: datetime) -> bool:
        return self._decide(deal_id, user_id, DealInvitationStatus.ACCEPTED, now)

    def decline(self, deal_id: UUID, user_id: UUID, now: datetime) -> bool:
        return self._decide(deal_id, user_id, DealInvitationStatus.DECLINED, now)

    def close_open(self, deal_ids: Sequence[UUID]) -> None:
        if not deal_ids:
            return
        self._db.execute(
            update(DealInvitation)
            .where(
                DealInvitation.deal_id.in_(deal_ids),
                DealInvitation.status == DealInvitationStatus.INVITED,
            )
            .values(status=DealInvitationStatus.CLOSED)
            .execution_options(synchronize_session=False)
        )

    def _decide(
        self, deal_id: UUID, user_id: UUID, status: DealInvitationStatus, now: datetime
    ) -> bool:
        result = self._db.execute(
            update(DealInvitation)
            .where(
                DealInvitation.deal_id == deal_id,
                DealInvitation.user_id == user_id,
                DealInvitation.status == DealInvitationStatus.INVITED,
            )
            .values(status=status, decided_at=now)
            .returning(DealInvitation.id)
            .execution_options(synchronize_session=False)
        )
        return result.first() is not None
