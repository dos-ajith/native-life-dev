from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import NativePlaceMessages
from app.models.user import User
from app.repositories.gis_village_repository import GisVillageRepository
from app.repositories.post_repository import AreaPoint
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.update_feed import UpdateAreaSource


@dataclass(frozen=True)
class FeedArea:
    source: UpdateAreaSource
    point: AreaPoint


class NativeAreaResolver:
    def __init__(self, db: Session) -> None:
        self._places = UserNativePlaceRepository(db)
        self._villages = GisVillageRepository(db)

    def native_areas(self, viewer: User) -> list[FeedArea]:
        return [
            self._area(UpdateAreaSource(place.slot.value), place.village_id)
            for place in self._places.list_by_user(viewer.id)
        ]

    def temporary_area(self, village_id: UUID) -> FeedArea:
        return self._area(UpdateAreaSource.TEMPORARY, village_id)

    def required_areas(self, viewer: User, temporary_village_id: UUID | None) -> list[FeedArea]:
        if temporary_village_id is not None:
            return [self.temporary_area(temporary_village_id)]
        areas = self.native_areas(viewer)
        if not areas:
            raise BusinessRuleError(NativePlaceMessages.PRIMARY_REQUIRED)
        return areas

    def _area(self, source: UpdateAreaSource, village_id: UUID) -> FeedArea:
        point = self._villages.get_representative_point(village_id)
        if point is None:
            raise NotFoundError(NativePlaceMessages.VILLAGE_NOT_FOUND)
        return FeedArea(source, AreaPoint(*point))
