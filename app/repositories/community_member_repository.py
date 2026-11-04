from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.community_member import CommunityMember, CommunityMemberStatus
from app.schemas.pagination import PaginationParams


class CommunityMemberRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, community_id: UUID, user_id: UUID) -> CommunityMember | None:
        return self._db.scalar(
            select(CommunityMember).where(
                CommunityMember.community_id == community_id, CommunityMember.user_id == user_id
            )
        )

    def is_active_member(self, community_id: UUID, user_id: UUID) -> bool:
        member = self.get(community_id, user_id)
        return member is not None and member.status == CommunityMemberStatus.ACTIVE

    def list_active_user_ids(self, community_id: UUID) -> list[UUID]:
        return list(
            self._db.scalars(
                select(CommunityMember.user_id).where(
                    CommunityMember.community_id == community_id,
                    CommunityMember.status == CommunityMemberStatus.ACTIVE,
                )
            )
        )

    def mark_read(self, community_id: UUID, user_id: UUID) -> None:
        self._db.execute(
            update(CommunityMember)
            .where(
                CommunityMember.community_id == community_id,
                CommunityMember.user_id == user_id,
                CommunityMember.status == CommunityMemberStatus.ACTIVE,
            )
            .values(last_read_at=func.now())
        )
        self._db.commit()

    def stage(self, member: CommunityMember) -> CommunityMember:
        self._db.add(member)
        self._db.flush()
        return member

    def stage_delete(self, member: CommunityMember) -> None:
        self._db.delete(member)
        self._db.flush()

    def list_by_status(
        self, community_id: UUID, status: CommunityMemberStatus, params: PaginationParams
    ) -> tuple[list[CommunityMember], int]:
        conditions = [
            CommunityMember.community_id == community_id,
            CommunityMember.status == status,
        ]
        total = self._db.scalar(
            select(func.count()).select_from(CommunityMember).where(*conditions)
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(CommunityMember)
            .options(joinedload(CommunityMember.user))
            .where(*conditions)
            .order_by(CommunityMember.created_at, CommunityMember.id)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total or 0

    def status_by_community(
        self, user_id: UUID, community_ids: list[UUID]
    ) -> dict[UUID, CommunityMemberStatus]:
        rows = self._db.execute(
            select(CommunityMember.community_id, CommunityMember.status).where(
                CommunityMember.user_id == user_id,
                CommunityMember.community_id.in_(community_ids),
            )
        ).all()
        return {community_id: status for community_id, status in rows}
