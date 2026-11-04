from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import NativePlaceMessages
from app.models.gis_village import GisVillage
from app.models.user import User
from app.models.user_native_place import NativePlaceSlot
from app.repositories.gis_village_repository import GisVillageRepository, VillageBoundary
from app.repositories.user_native_place_repository import UserNativePlaceRepository


@dataclass(frozen=True)
class VillageBoundaryResult:
    village: GisVillage
    boundary: VillageBoundary


class VillageBoundaryService:
    def __init__(self, db: Session) -> None:
        self._villages = GisVillageRepository(db)
        self._native_places = UserNativePlaceRepository(db)

    def for_village(self, village_id: UUID) -> VillageBoundaryResult:
        village = self._villages.get_by_id_without_geometry(village_id)
        boundary = self._villages.get_boundary(village_id) if village is not None else None
        if village is None or boundary is None:
            raise NotFoundError(NativePlaceMessages.VILLAGE_NOT_FOUND)
        return VillageBoundaryResult(village=village, boundary=boundary)

    def for_user(self, user: User) -> list[tuple[NativePlaceSlot, VillageBoundaryResult]]:
        places = self._native_places.list_by_user(user.id)
        return [(place.slot, self.for_village(place.village_id)) for place in places]
