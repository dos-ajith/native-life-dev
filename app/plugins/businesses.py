from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_native_place import NativePlaceSlot
from app.plugins.deps import PluginBusiness
from app.repositories.business_repository import BusinessRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.gis_village_repository import GisVillageRepository
from app.repositories.user_native_place_repository import UserNativePlaceRepository


@dataclass(frozen=True)
class NativeOrigin:
    name: str
    latitude: float
    longitude: float


def find_plugin_business(db: Session, business_id: UUID) -> PluginBusiness | None:
    business = BusinessRepository(db).get_by_id(business_id)
    if business is None:
        return None
    return PluginBusiness(
        id=business.id,
        owner_id=business.owner_id,
        name=business.name,
        category_id=business.category_id,
    )


def category_slugs_for_businesses(
    db: Session, business_ids: Collection[UUID]
) -> dict[UUID, frozenset[str]]:
    businesses = BusinessRepository(db)
    categories = CategoryRepository(db)
    chains: dict[UUID, frozenset[str]] = {}
    result: dict[UUID, frozenset[str]] = {}
    for business_id in business_ids:
        business = businesses.get_by_id(business_id)
        if business is None or business.category_id is None:
            result[business_id] = frozenset()
            continue
        if business.category_id not in chains:
            chains[business.category_id] = frozenset(
                category.slug for category in categories.get_chain(business.category_id)
            )
        result[business_id] = chains[business.category_id]
    return result


def find_native_origin(db: Session, user: User) -> NativeOrigin | None:
    places = UserNativePlaceRepository(db).list_by_user(user.id)
    if not places:
        return None
    place = next((item for item in places if item.slot == NativePlaceSlot.PRIMARY), places[0])
    point = GisVillageRepository(db).get_representative_point(place.village_id)
    if point is None:
        return None
    return NativeOrigin(name=place.village.name, latitude=point[0], longitude=point[1])
