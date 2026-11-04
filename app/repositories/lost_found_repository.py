from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, literal, null, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.gis_village import GisVillage
from app.models.lost_found_item import LostFoundItem, LostFoundKind, LostFoundStatus
from app.models.user import User, UserStatus
from app.models.user_content_settings import UserContentSettings
from app.models.user_native_place import UserNativePlace
from app.models.user_settings_defaults import UserSettingsDefaults
from app.repositories.post_repository import AreaPoint
from app.repositories.spatial import as_geography, point_from_coordinates
from app.schemas.pagination import PaginationParams

NO_AREA_RANK = -1
METERS_PER_KM = 1000


class LostFoundRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, item_id: UUID) -> LostFoundItem | None:
        return self._db.scalar(
            select(LostFoundItem)
            .options(joinedload(LostFoundItem.category))
            .where(LostFoundItem.id == item_id, LostFoundItem.deleted_at.is_(None))
        )

    def list_reports(
        self,
        params: PaginationParams,
        status: LostFoundStatus,
        kind: LostFoundKind | None,
        category_id: UUID | None,
        query: str | None,
        areas: Sequence[AreaPoint],
        radius_meters: float,
        restrict_to_areas: bool,
    ) -> tuple[Sequence[tuple[LostFoundItem, int, float | None]], int]:
        location = as_geography(LostFoundItem.location)
        points = [as_geography(point_from_coordinates(a.latitude, a.longitude)) for a in areas]
        within = [func.ST_DWithin(location, point, radius_meters) for point in points]
        conditions: list[ColumnElement[bool]] = [
            LostFoundItem.deleted_at.is_(None),
            LostFoundItem.status == status,
        ]
        if kind is not None:
            conditions.append(LostFoundItem.kind == kind)
        if category_id is not None:
            conditions.append(LostFoundItem.category_id == category_id)
        if query:
            pattern = f"%{query}%"
            conditions.append(
                or_(
                    LostFoundItem.title.ilike(pattern),
                    LostFoundItem.description.ilike(pattern),
                    LostFoundItem.location_name.ilike(pattern),
                )
            )
        rank: ColumnElement[int] = literal(NO_AREA_RANK)
        distance: ColumnElement[Any] = null()
        if within:
            rank = case(*((condition, index) for index, condition in enumerate(within)))
            distance = case(
                *(
                    (condition, func.ST_Distance(location, point))
                    for condition, point in zip(within, points, strict=True)
                )
            )
        order: list[Any] = [LostFoundItem.created_at.desc(), LostFoundItem.id]
        if within:
            if restrict_to_areas:
                conditions.append(or_(*within))
            order = [rank, *order]
        total = (
            self._db.scalar(select(func.count()).select_from(LostFoundItem).where(*conditions)) or 0
        )
        offset = (params.page - 1) * params.page_size
        rows = self._db.execute(
            select(LostFoundItem, rank.label("area_rank"), distance.label("distance_meters"))
            .options(joinedload(LostFoundItem.category))
            .where(*conditions)
            .order_by(*order)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return [(item, area_rank, meters) for item, area_rank, meters in rows], total

    def list_nearby_user_ids(
        self, latitude: float, longitude: float, exclude_user_id: UUID, limit: int
    ) -> list[UUID]:
        village_point = as_geography(func.ST_PointOnSurface(GisVillage.geom))
        item_point = as_geography(point_from_coordinates(latitude, longitude))
        radius_meters = (
            func.coalesce(
                UserContentSettings.nearby_radius_km, UserSettingsDefaults.NEARBY_RADIUS_KM
            )
            * METERS_PER_KM
        )
        return list(
            self._db.scalars(
                select(UserNativePlace.user_id)
                .join(User, User.id == UserNativePlace.user_id)
                .join(GisVillage, GisVillage.id == UserNativePlace.village_id)
                .outerjoin(UserContentSettings, UserContentSettings.user_id == User.id)
                .where(
                    User.deleted_at.is_(None),
                    User.status == UserStatus.ACTIVE,
                    User.id != exclude_user_id,
                    func.ST_DWithin(village_point, item_point, radius_meters),
                )
                .distinct()
                .order_by(UserNativePlace.user_id)
                .limit(limit)
            )
        )

    def add(self, item: LostFoundItem) -> LostFoundItem:
        self._db.add(item)
        self._db.commit()
        self._db.refresh(item)
        return item

    def save(self, item: LostFoundItem) -> LostFoundItem:
        self._db.commit()
        self._db.refresh(item)
        return item
