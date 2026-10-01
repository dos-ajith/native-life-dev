from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.role_upgrade_request import RoleUpgradeRequest, RoleUpgradeRequestStatus
from app.schemas.pagination import PaginationParams


class RoleUpgradeRequestRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_pending(self, user_id: UUID, requested_role_id: UUID) -> RoleUpgradeRequest | None:
        created_id = self._db.scalar(
            insert(RoleUpgradeRequest)
            .values(user_id=user_id, requested_role_id=requested_role_id)
            .on_conflict_do_nothing(
                index_elements=[
                    RoleUpgradeRequest.user_id,
                    RoleUpgradeRequest.requested_role_id,
                ],
                index_where=text("status = 'pending'"),
            )
            .returning(RoleUpgradeRequest.id)
        )
        self._db.commit()
        if created_id is None:
            return None
        return self.get_by_id(created_id)

    def get_by_id(self, request_id: UUID) -> RoleUpgradeRequest | None:
        return self._db.get(RoleUpgradeRequest, request_id)

    def get_by_id_for_user(self, request_id: UUID, user_id: UUID) -> RoleUpgradeRequest | None:
        return self._db.scalar(
            select(RoleUpgradeRequest).where(
                RoleUpgradeRequest.id == request_id, RoleUpgradeRequest.user_id == user_id
            )
        )

    def list_by_user(
        self, user_id: UUID, params: PaginationParams
    ) -> tuple[list[RoleUpgradeRequest], int]:
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(RoleUpgradeRequest)
                .where(RoleUpgradeRequest.user_id == user_id)
            )
            or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(RoleUpgradeRequest)
            .where(RoleUpgradeRequest.user_id == user_id)
            .order_by(RoleUpgradeRequest.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def list_pending(self, params: PaginationParams) -> tuple[list[RoleUpgradeRequest], int]:
        pending = RoleUpgradeRequest.status == RoleUpgradeRequestStatus.PENDING
        total = (
            self._db.scalar(select(func.count()).select_from(RoleUpgradeRequest).where(pending))
            or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(RoleUpgradeRequest)
            .where(pending)
            .order_by(RoleUpgradeRequest.created_at.asc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def save(self, request: RoleUpgradeRequest) -> RoleUpgradeRequest:
        self._db.commit()
        self._db.refresh(request)
        return request
