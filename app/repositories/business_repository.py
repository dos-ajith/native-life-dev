from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy.sql.base import ExecutableOption

from app.core.timezone import app_now
from app.models.business import Business, BusinessStatus, BusinessVerificationStatus
from app.models.business_document import BusinessDocument
from app.models.business_image import BusinessImage
from app.models.category import Category
from app.models.gis_village import GisVillage
from app.models.user import User
from app.repositories.category_repository import category_subtree_ids, unavailable_category_tree_ids
from app.repositories.spatial import as_geography, point_from_coordinates
from app.schemas.business import BusinessDiscoveryQuery
from app.schemas.business_review import BusinessReviewQuery, BusinessReviewScope
from app.schemas.pagination import PaginationParams


@dataclass(frozen=True)
class BusinessDiscoveryRow:
    id: UUID
    name: str
    description: str | None
    category_id: UUID
    category_name: str
    parent_category_id: UUID | None
    parent_category_name: str | None
    distance_meters: float | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class BusinessCounts:
    registered: int
    active: int
    pending_verification: int
    routine_local: int
    platform_escalation: int


def _with_category() -> ExecutableOption:
    return joinedload(Business.category).joinedload(Category.parent)


class BusinessRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, business_id: UUID) -> Business | None:
        return self._db.scalar(
            select(Business)
            .options(_with_category())
            .where(Business.id == business_id, Business.deleted_at.is_(None))
        )

    def list_by_owner(self, owner_id: UUID, params: PaginationParams) -> tuple[list[Business], int]:
        conditions = [Business.owner_id == owner_id, Business.deleted_at.is_(None)]
        total = self._count(conditions)
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Business)
            .options(_with_category())
            .where(*conditions)
            .order_by(Business.name.asc(), Business.id.asc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def search_active(
        self, query: BusinessDiscoveryQuery, params: PaginationParams
    ) -> tuple[list[BusinessDiscoveryRow], int]:
        conditions = _discovery_conditions(query)
        total = self._count(conditions)
        parent = aliased(Category)
        offset = (params.page - 1) * params.page_size
        columns: list[Any] = [
            Business.id,
            Business.name,
            Business.description,
            Category.id,
            Category.name,
            parent.id,
            parent.name,
        ]
        order: list[Any] = [Business.name.asc(), Business.id.asc()]
        if query.has_location:
            distance = _distance_from(query)
            columns.append(distance)
            order = [distance.asc(), *order]
        columns.append(_first_image_url())
        rows = self._db.execute(
            select(*columns)
            .join(Category, Category.id == Business.category_id)
            .outerjoin(parent, parent.id == Category.parent_id)
            .where(*conditions)
            .order_by(*order)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return [_to_discovery_row(row, query.has_location) for row in rows], total

    def exists_listed_within(self, latitude: float, longitude: float, radius_meters: int) -> bool:
        point = as_geography(point_from_coordinates(latitude, longitude))
        conditions = [*_listed_conditions(), _within_radius(point, radius_meters)]
        return bool(self._db.scalar(select(exists().where(*conditions))))

    def add(self, business: Business) -> Business:
        self._db.add(business)
        self._db.commit()
        return self._reload(business.id)

    def add_with_attachments(
        self,
        business: Business,
        images: list[BusinessImage],
        documents: list[BusinessDocument],
    ) -> Business:
        self._db.add(business)
        self._db.flush()
        for image in images:
            image.business_id = business.id
        for document in documents:
            document.business_id = business.id
        self._db.add_all([*images, *documents])
        self._db.commit()
        return self._reload(business.id)

    def owner_has_named(self, owner_id: UUID, name: str, excluding_id: UUID | None = None) -> bool:
        conditions = [
            Business.owner_id == owner_id,
            Business.deleted_at.is_(None),
            func.lower(Business.name) == name.lower(),
        ]
        if excluding_id is not None:
            conditions.append(Business.id != excluding_id)
        return bool(self._db.scalar(select(exists().where(*conditions))))

    def has_pending_verification_for_owner(self, owner_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    exists().where(
                        Business.owner_id == owner_id,
                        Business.verification_status == BusinessVerificationStatus.PENDING,
                        Business.deleted_at.is_(None),
                    )
                )
            )
        )

    def list_for_review(
        self, query: BusinessReviewQuery, params: PaginationParams, village_id: UUID | None
    ) -> tuple[list[Business], int]:
        conditions = _review_conditions(query, village_id)
        total = self._count(conditions)
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Business)
            .options(_with_category(), joinedload(Business.owner))
            .where(*conditions)
            .order_by(Business.created_at.desc(), Business.id.asc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def list_all_for_review(
        self, query: BusinessReviewQuery, village_id: UUID | None
    ) -> list[Business]:
        return list(
            self._db.scalars(
                select(Business)
                .options(_with_category(), joinedload(Business.owner))
                .where(*_review_conditions(query, village_id))
                .order_by(Business.created_at.desc(), Business.id.asc())
            ).all()
        )

    def count_for_review(self, village_id: UUID | None) -> BusinessCounts:
        conditions = _review_conditions(BusinessReviewQuery(), village_id)
        registered, active, pending, routine_local, platform_escalation = self._db.execute(
            select(
                func.count(),
                func.count().filter(Business.status == BusinessStatus.ACTIVE),
                func.count().filter(_is_pending()),
                func.count().filter(_is_pending(), Business.escalated_at.is_(None)),
                func.count().filter(_is_pending(), Business.escalated_at.is_not(None)),
            )
            .select_from(Business)
            .where(*conditions)
        ).one()
        return BusinessCounts(
            registered=registered,
            active=active,
            pending_verification=pending,
            routine_local=routine_local,
            platform_escalation=platform_escalation,
        )

    def is_within_village(self, business_id: UUID, village_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    exists().where(
                        Business.id == business_id,
                        Business.location.is_not(None),
                        _within_village(village_id),
                    )
                )
            )
        )

    def point_is_within_village(self, latitude: float, longitude: float, village_id: UUID) -> bool:
        village_geometry = (
            select(GisVillage.geom).where(GisVillage.id == village_id).scalar_subquery()
        )
        point = point_from_coordinates(latitude, longitude)
        return bool(self._db.scalar(select(func.ST_Contains(village_geometry, point))))

    def rollback(self) -> None:
        self._db.rollback()

    def save(self, business: Business) -> Business:
        self._db.commit()
        return self._reload(business.id)

    def soft_delete(self, business: Business) -> None:
        business.deleted_at = app_now()
        self._db.commit()

    def _reload(self, business_id: UUID) -> Business:
        return self._db.execute(
            select(Business).options(_with_category()).where(Business.id == business_id)
        ).scalar_one()

    def _count(self, conditions: list[ColumnElement[bool]]) -> int:
        return self._db.scalar(select(func.count()).select_from(Business).where(*conditions)) or 0


def _within_village(village_id: UUID) -> ColumnElement[bool]:
    village_geometry = select(GisVillage.geom).where(GisVillage.id == village_id).scalar_subquery()
    return func.ST_Contains(village_geometry, Business.location)


def _first_image_url() -> Any:
    return (
        select(BusinessImage.image_url)
        .where(BusinessImage.business_id == Business.id)
        .order_by(BusinessImage.sort_order, BusinessImage.created_at)
        .limit(1)
        .scalar_subquery()
    )


def _to_discovery_row(row: Any, has_distance: bool) -> BusinessDiscoveryRow:
    values = list(row)
    image_url = values.pop()
    distance = values.pop() if has_distance else None
    business_id, name, description, category_id, category_name, parent_id, parent_name = values
    return BusinessDiscoveryRow(
        id=business_id,
        name=name,
        description=description,
        category_id=category_id,
        category_name=category_name,
        parent_category_id=parent_id,
        parent_category_name=parent_name,
        distance_meters=distance,
        image_url=image_url,
    )


def _is_pending() -> ColumnElement[bool]:
    return Business.verification_status == BusinessVerificationStatus.PENDING


def _review_conditions(
    query: BusinessReviewQuery, village_id: UUID | None
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [Business.deleted_at.is_(None)]
    if village_id is not None:
        conditions.append(_within_village(village_id))
    if query.village_id is not None:
        conditions.append(_within_village(query.village_id))
    if query.owner_id is not None:
        conditions.append(Business.owner_id == query.owner_id)
    if query.scope == BusinessReviewScope.ROUTINE_LOCAL:
        conditions.extend([_is_pending(), Business.escalated_at.is_(None)])
    if query.scope == BusinessReviewScope.PLATFORM_ESCALATION:
        conditions.extend([_is_pending(), Business.escalated_at.is_not(None)])
    if query.verification_status is not None:
        conditions.append(Business.verification_status == query.verification_status)
    if query.status is not None:
        conditions.append(Business.status == query.status)
    if query.category_id is not None:
        conditions.append(Business.category_id.in_(category_subtree_ids(query.category_id)))
    term = query.search.strip() if query.search is not None else ""
    if term:
        owner_ids = select(User.id).where(
            or_(
                func.concat(User.first_name, " ", User.last_name).icontains(term, autoescape=True),
                User.email.icontains(term, autoescape=True),
            )
        )
        conditions.append(
            or_(Business.name.icontains(term, autoescape=True), Business.owner_id.in_(owner_ids))
        )
    return conditions


def _search_point(query: BusinessDiscoveryQuery) -> Any:
    assert query.latitude is not None and query.longitude is not None
    return as_geography(point_from_coordinates(query.latitude, query.longitude))


def _distance_from(query: BusinessDiscoveryQuery) -> Any:
    return func.ST_Distance(as_geography(Business.location), _search_point(query)).label(
        "distance_meters"
    )


def _within_radius(point: Any, radius_meters: int) -> ColumnElement[bool]:
    return func.ST_DWithin(as_geography(Business.location), point, radius_meters)


def _listed_conditions() -> list[ColumnElement[bool]]:
    return [
        Business.deleted_at.is_(None),
        Business.status == BusinessStatus.ACTIVE,
        Business.owner_id.in_(select(User.id).where(User.deleted_at.is_(None))),
        Business.category_id.is_not(None),
        Business.category_id.not_in(unavailable_category_tree_ids()),
    ]


def _discovery_conditions(query: BusinessDiscoveryQuery) -> list[ColumnElement[bool]]:
    conditions = _listed_conditions()
    if query.search is not None and query.search.strip():
        conditions.append(Business.name.ilike(f"%{query.search.strip()}%"))
    if query.category_id is not None:
        conditions.append(Business.category_id.in_(category_subtree_ids(query.category_id)))
    if query.village_id is not None:
        conditions.append(_within_village(query.village_id))
    if query.has_location:
        conditions.append(_within_radius(_search_point(query), query.effective_radius_meters))
    return conditions
