from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.gis_district import GisDistrict
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.models.user_native_place import NativePlaceSlot, UserNativePlace


@dataclass(frozen=True)
class NativePlaceHierarchy:
    slot: NativePlaceSlot
    village_id: UUID
    taluk_id: UUID
    district_id: UUID


class UserNativePlaceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(self, user_id: UUID) -> list[UserNativePlace]:
        stmt = (
            select(UserNativePlace)
            .options(
                joinedload(UserNativePlace.village)
                .joinedload(GisVillage.taluk)
                .joinedload(GisTaluk.district)
                .joinedload(GisDistrict.state)
            )
            .where(UserNativePlace.user_id == user_id)
            .order_by(UserNativePlace.slot)
        )
        return list(self._db.scalars(stmt))

    def list_hierarchy(self, user_id: UUID) -> list[NativePlaceHierarchy]:
        rows = self._db.execute(
            select(
                UserNativePlace.slot,
                GisVillage.id,
                GisVillage.taluk_id,
                GisTaluk.district_id,
            )
            .join(GisVillage, GisVillage.id == UserNativePlace.village_id)
            .join(GisTaluk, GisTaluk.id == GisVillage.taluk_id)
            .where(UserNativePlace.user_id == user_id)
        ).all()
        return [
            NativePlaceHierarchy(
                slot=slot, village_id=village_id, taluk_id=taluk_id, district_id=district_id
            )
            for slot, village_id, taluk_id, district_id in rows
        ]

    def get_by_slot(self, user_id: UUID, slot: NativePlaceSlot) -> UserNativePlace | None:
        stmt = select(UserNativePlace).where(
            UserNativePlace.user_id == user_id, UserNativePlace.slot == slot
        )
        return self._db.scalars(stmt).first()

    def add(self, place: UserNativePlace) -> UserNativePlace:
        self._db.add(place)
        self._db.commit()
        return place

    def save(self, place: UserNativePlace) -> UserNativePlace:
        self._db.commit()
        return place

    def delete(self, place: UserNativePlace) -> None:
        self._db.delete(place)
        self._db.commit()
