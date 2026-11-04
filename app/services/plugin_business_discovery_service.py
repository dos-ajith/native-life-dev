from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.user import User
from app.repositories.business_plugin_repository import BusinessPluginRepository
from app.services.native_area_resolver import NativeAreaResolver
from app.services.user_settings_service import UserSettingsService

METERS_PER_KM = 1000
NEARBY_BUSINESS_LIMIT = 200


@dataclass(frozen=True)
class NearbyBusiness:
    id: UUID
    name: str
    distance_km: float


@dataclass(frozen=True)
class NativeBusinessScope:
    has_native_place: bool
    businesses: tuple[NearbyBusiness, ...]


def find_businesses_near_native_places(
    db: Session, user: User, plugin_key: str, village_id: UUID | None = None
) -> NativeBusinessScope:
    resolver = NativeAreaResolver(db)
    businesses = BusinessPluginRepository(db)
    if village_id is not None:
        origin = resolver.temporary_area(village_id).point
        rows = businesses.list_serving_in_village(
            plugin_key, village_id, origin, NEARBY_BUSINESS_LIMIT
        )
        return _scope(rows)
    areas = [area.point for area in resolver.native_areas(user)]
    if not areas:
        return NativeBusinessScope(has_native_place=False, businesses=())
    radius_km = UserSettingsService(db).nearby_radius_km(user)
    rows = businesses.list_nearby_serving(
        plugin_key, areas, radius_km * METERS_PER_KM, NEARBY_BUSINESS_LIMIT
    )
    return _scope(rows)


def _scope(rows: list[tuple[Business, float]]) -> NativeBusinessScope:
    return NativeBusinessScope(
        has_native_place=True,
        businesses=tuple(
            NearbyBusiness(
                id=business.id, name=business.name, distance_km=round(meters / METERS_PER_KM, 1)
            )
            for business, meters in rows
        ),
    )
