from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.role_upgrade_request import RoleUpgradeRequest, RoleUpgradeRequestStatus
from app.schemas.pagination import PaginationParams


class RoleUpgradeRequestRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def stage_pending(self, user_id: UUID, requested_role_id: UUID) -> RoleUpgradeRequest | None:
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
        if created_id is None:
            return None
        return self.get_by_id(created_id)

    def get_by_id(self, request_id: UUID) -> RoleUpgradeRequest | None:
        return self._db.get(RoleUpgradeRequest, request_id)

    def get_for_update(self, request_id: UUID) -> RoleUpgradeRequest | None:
        return self._db.get(RoleUpgradeRequest, request_id, with_for_update=True)

    def cancel_pending_for_user(self, user_id: UUID) -> list[RoleUpgradeRequest]:
        pending = list(
            self._db.scalars(
                select(RoleUpgradeRequest)
                .where(
                    RoleUpgradeRequest.user_id == user_id,
                    RoleUpgradeRequest.status == RoleUpgradeRequestStatus.PENDING,
                )
                .with_for_update()
            )
        )
        for request in pending:
            request.status = RoleUpgradeRequestStatus.CANCELLED
        self._db.flush()
        return pending

    def list_for_users(self, user_ids: Sequence[UUID]) -> list[RoleUpgradeRequest]:
        if not user_ids:
            return []
        return list(
            self._db.scalars(
                select(RoleUpgradeRequest)
                .where(RoleUpgradeRequest.user_id.in_(user_ids))
                .order_by(RoleUpgradeRequest.created_at.desc())
            )
        )

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

    def list_pending(
        self, params: PaginationParams, role_slugs: frozenset[str] | None = None
    ) -> tuple[list[RoleUpgradeRequest], int]:
        conditions = [RoleUpgradeRequest.status == RoleUpgradeRequestStatus.PENDING]
        if role_slugs is not None:
            conditions.append(
                RoleUpgradeRequest.requested_role_id.in_(
                    select(Role.id).where(Role.slug.in_(role_slugs))
                )
            )
        total = (
            self._db.scalar(select(func.count()).select_from(RoleUpgradeRequest).where(*conditions))
            or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(RoleUpgradeRequest)
            .where(*conditions)
            .order_by(RoleUpgradeRequest.created_at.asc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def save(self, request: RoleUpgradeRequest) -> RoleUpgradeRequest:
        self._db.commit()
        self._db.refresh(request)
        return request
