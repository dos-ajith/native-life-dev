from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, case, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.community import Community, CommunityStatus
from app.models.community_member import CommunityMember, CommunityMemberStatus
from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.schemas.pagination import PaginationParams

_WITH_PLACE = (
    joinedload(Community.owner),
    joinedload(Community.village)
    .defer(GisVillage.geom)
    .joinedload(GisVillage.taluk)
    .defer(GisTaluk.geom)
    .joinedload(GisTaluk.district)
    .defer(GisDistrict.geom)
    .joinedload(GisDistrict.state)
    .defer(GisState.geom),
)


@dataclass(frozen=True)
class PlaceIds:
    village_id: UUID
    taluk_id: UUID
    district_id: UUID


class CommunityRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, community_id: UUID) -> Community | None:
        return self._db.get(Community, community_id, options=_WITH_PLACE)

    def list_by_ids(self, community_ids: list[UUID]) -> list[Community]:
        return list(
            self._db.scalars(select(Community).where(Community.id.in_(community_ids))).all()
        )

    def get_for_update(self, community_id: UUID) -> Community | None:
        return self._db.scalar(
            select(Community)
            .where(Community.id == community_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def is_published(community: Community) -> bool:
        return community.status == CommunityStatus.PUBLISHED

    def exists_with_name(self, name: str, exclude_id: UUID | None = None) -> bool:
        conditions: list[ColumnElement[bool]] = [
            func.lower(Community.name) == name.lower(),
            Community.status != CommunityStatus.REJECTED,
        ]
        if exclude_id is not None:
            conditions.append(Community.id != exclude_id)
        return bool(self._db.scalar(select(exists().where(*conditions))))

    def owner_has_pending(self, owner_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    exists().where(
                        Community.owner_id == owner_id,
                        Community.status == CommunityStatus.PENDING,
                    )
                )
            )
        )

    def list_pending_ids_by_owner(self, owner_id: UUID) -> list[UUID]:
        return list(
            self._db.scalars(
                select(Community.id).where(
                    Community.owner_id == owner_id,
                    Community.status == CommunityStatus.PENDING,
                )
            )
        )

    def add(self, community: Community) -> Community:
        self._db.add(community)
        self._db.commit()
        self._db.refresh(community)
        return community

    def save(self, community: Community) -> Community:
        self._db.commit()
        self._db.refresh(community)
        return community

    def search_published(
        self, query: str | None, params: PaginationParams
    ) -> tuple[list[Community], int]:
        conditions: list[ColumnElement[bool]] = [Community.status == CommunityStatus.PUBLISHED]
        if query is not None:
            conditions.append(Community.name.ilike(f"%{query}%"))
        return self._paginate(conditions, params, Community.members_count.desc())

    def list_recommended(
        self, user_id: UUID, places: Sequence[PlaceIds], params: PaginationParams
    ) -> tuple[list[tuple[Community, int]], int]:
        if not places:
            return [], 0
        steps: list[tuple[ColumnElement[bool], int]] = []
        for index, place in enumerate(places):
            steps.append((Community.village_id == place.village_id, index))
            steps.append((GisVillage.taluk_id == place.taluk_id, len(places) + index))
            steps.append((GisTaluk.district_id == place.district_id, 2 * len(places) + index))
        steps.sort(key=lambda step: step[1])
        rank = case(*steps, else_=len(steps))
        already_related = exists().where(
            CommunityMember.community_id == Community.id, CommunityMember.user_id == user_id
        )
        conditions: list[ColumnElement[bool]] = [
            Community.status == CommunityStatus.PUBLISHED,
            Community.owner_id != user_id,
            ~already_related,
            or_(*(condition for condition, _ in steps)),
        ]
        joined = (
            select(Community, rank.label("rank"))
            .join(GisVillage, GisVillage.id == Community.village_id)
            .join(GisTaluk, GisTaluk.id == GisVillage.taluk_id)
            .where(*conditions)
        )
        total = self._db.scalar(
            select(func.count())
            .select_from(Community)
            .join(GisVillage, GisVillage.id == Community.village_id)
            .join(GisTaluk, GisTaluk.id == GisVillage.taluk_id)
            .where(*conditions)
        )
        offset = (params.page - 1) * params.page_size
        rows = self._db.execute(
            joined.options(*_WITH_PLACE)
            .order_by(
                rank, Community.members_count.desc(), Community.created_at.desc(), Community.id
            )
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return [(community, rank_value) for community, rank_value in rows], total or 0

    def list_pending(self, params: PaginationParams) -> tuple[list[Community], int]:
        return self._paginate(
            [Community.status == CommunityStatus.PENDING], params, Community.created_at.asc()
        )

    def list_for_user(self, user_id: UUID, params: PaginationParams) -> tuple[list[Community], int]:
        member_of = select(CommunityMember.community_id).where(
            CommunityMember.user_id == user_id,
            CommunityMember.status == CommunityMemberStatus.ACTIVE,
        )
        return self._paginate(
            [or_(Community.owner_id == user_id, Community.id.in_(member_of))],
            params,
            Community.created_at.desc(),
        )

    def _paginate(
        self,
        conditions: list[ColumnElement[bool]],
        params: PaginationParams,
        order: ColumnElement[Any],
    ) -> tuple[list[Community], int]:
        total = self._db.scalar(select(func.count()).select_from(Community).where(*conditions))
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Community)
            .options(*_WITH_PLACE)
            .where(*conditions)
            .order_by(order, Community.id)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total or 0
