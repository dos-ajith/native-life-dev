from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.messages import UserAddressMessages
from app.models.gis_village import GisVillage
from app.models.user import User
from app.models.user_address import UserAddress
from app.models.user_native_place import NativePlaceSlot
from app.repositories.gis_village_repository import GisVillageRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.spatial import point_from_coordinates
from app.repositories.user_address_repository import UserAddressRepository
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.user_address import UserAddressCreate, UserAddressUpdate
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "user_address"
NULLABLE_FIELDS = frozenset({"landmark"})
LOCATION_FIELDS = frozenset({"latitude", "longitude"})


@dataclass(frozen=True)
class AddressMapCenter:
    latitude: float
    longitude: float
    village: GisVillage


def format_shipping_address(address: UserAddress) -> str:
    district = address.village.taluk.district
    parts = [
        address.full_name,
        address.address_line,
        address.landmark,
        address.village.name,
        district.name,
        f"{district.state.name} {address.pincode}",
        address.phone,
    ]
    return ", ".join(part for part in parts if part)


class UserAddressService:
    def __init__(self, db: Session) -> None:
        self._addresses = UserAddressRepository(db)
        self._villages = GisVillageRepository(db)
        self._native_places = UserNativePlaceRepository(db)
        self._orders = OrderRepository(db)
        self._activity_logs = ActivityLogService(db)

    def list_for(self, actor: User) -> list[UserAddress]:
        return self._addresses.list_by_user(actor.id)

    def get_owned(self, address_id: UUID, actor: User) -> UserAddress:
        address = self._addresses.get_by_id(address_id)
        if address is None or address.user_id != actor.id:
            raise NotFoundError(UserAddressMessages.NOT_FOUND)
        return address

    def map_center(self, actor: User) -> AddressMapCenter:
        primary = self._native_places.get_by_slot(actor.id, NativePlaceSlot.PRIMARY)
        village = self._villages.get_by_id(primary.village_id) if primary is not None else None
        point = self._villages.get_representative_point(village.id) if village is not None else None
        if village is None or point is None:
            raise NotFoundError(UserAddressMessages.NO_NATIVE_PLACE)
        return AddressMapCenter(latitude=point[0], longitude=point[1], village=village)

    def create(self, payload: UserAddressCreate, actor: User) -> UserAddress:
        village = self._village_at(payload.latitude, payload.longitude)
        is_first = self._addresses.count_by_user(actor.id) == 0
        make_default = payload.is_default or is_first
        if make_default:
            self._addresses.clear_default(actor.id)
        address = self._addresses.add(
            UserAddress(
                user_id=actor.id,
                **payload.model_dump(exclude={"is_default", "latitude", "longitude"}),
                village_id=village.id,
                location=point_from_coordinates(payload.latitude, payload.longitude),
                is_default=make_default,
            )
        )
        address_id = address.id
        self._addresses.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_ADDRESS_CREATED,
            entity_type=ENTITY_TYPE,
            entity_id=address_id,
        )
        return self.get_owned(address_id, actor)

    def update(self, address_id: UUID, payload: UserAddressUpdate, actor: User) -> UserAddress:
        address = self.get_owned(address_id, actor)
        data = {
            field: value
            for field, value in payload.model_dump(exclude_unset=True).items()
            if value is not None or field in NULLABLE_FIELDS
        }
        if payload.latitude is not None and payload.longitude is not None:
            village = self._village_at(payload.latitude, payload.longitude)
            address.village_id = village.id
            address.location = point_from_coordinates(payload.latitude, payload.longitude)
        for field, value in data.items():
            if field not in LOCATION_FIELDS:
                setattr(address, field, value)
        self._addresses.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_ADDRESS_UPDATED,
            entity_type=ENTITY_TYPE,
            entity_id=address_id,
            metadata={"updated_fields": list(data.keys())},
        )
        return self.get_owned(address_id, actor)

    def set_default(self, address_id: UUID, actor: User) -> UserAddress:
        address = self.get_owned(address_id, actor)
        if not address.is_default:
            self._addresses.clear_default(actor.id)
            address.is_default = True
            self._addresses.commit()
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.USER_ADDRESS_DEFAULT_SET,
                entity_type=ENTITY_TYPE,
                entity_id=address_id,
            )
        return self.get_owned(address_id, actor)

    def delete(self, address_id: UUID, actor: User) -> None:
        address = self.get_owned(address_id, actor)
        if self._orders.has_open_for_address(address.id):
            raise ConflictError(UserAddressMessages.HAS_ONGOING_ORDERS)
        was_default = address.is_default
        self._addresses.delete(address)
        if was_default:
            replacement = self._addresses.latest_by_user(actor.id)
            if replacement is not None:
                replacement.is_default = True
        self._addresses.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_ADDRESS_DELETED,
            entity_type=ENTITY_TYPE,
            entity_id=address_id,
        )

    def _village_at(self, latitude: float, longitude: float) -> GisVillage:
        village = self._villages.find_containing_point(latitude, longitude)
        if village is None:
            raise BusinessRuleError(UserAddressMessages.OUTSIDE_COVERAGE)
        return village
