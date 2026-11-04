from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import NativePlaceMessages
from app.models.gis_district import GisDistrict
from app.models.gis_village import GisVillage
from app.models.user import User
from app.models.user_native_place import NativePlaceSlot, UserNativePlace
from app.repositories.business_repository import BusinessRepository
from app.repositories.gis_district_repository import GisDistrictRepository
from app.repositories.gis_state_repository import GisStateRepository
from app.repositories.gis_village_repository import GisVillageRepository
from app.repositories.post_repository import PostRepository, PostVisibilityScope
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.user_settings_service import UserSettingsService

ENTITY_TYPE = "user_native_place"
FALLBACK_DISTRICTS_PARAMS = PaginationParams(page=1, page_size=100)
SECONDARY_ELIGIBILITY_RADIUS_KM = 30
METERS_PER_KM = 1000


@dataclass(frozen=True)
class NearbyArea:
    latitude: float
    longitude: float
    radius_km: int


@dataclass(frozen=True)
class SecondaryEligibility:
    is_eligible: bool
    radius_km: int
    has_nearby_businesses: bool
    has_nearby_posts: bool


@dataclass(frozen=True)
class PrimaryNativePlaceResult:
    places: list[UserNativePlace]
    secondary_eligibility: SecondaryEligibility


class UserNativePlaceService:
    def __init__(self, db: Session) -> None:
        self._villages = GisVillageRepository(db)
        self._districts = GisDistrictRepository(db)
        self._states = GisStateRepository(db)
        self._places = UserNativePlaceRepository(db)
        self._businesses = BusinessRepository(db)
        self._posts = PostRepository(db)
        self._settings = UserSettingsService(db)
        self._activity_logs = ActivityLogService(db)

    def search(
        self, query: str, limit: int, default_state_lgd_code: str
    ) -> tuple[list[GisVillage], list[GisDistrict]]:
        villages = self._villages.search_by_name(query.strip(), limit)
        if villages:
            return villages, []
        return [], self._fallback_districts(default_state_lgd_code)

    def resolve_current_location(self, latitude: float, longitude: float) -> GisVillage:
        village = self._villages.find_containing_point(latitude, longitude)
        if village is None:
            raise NotFoundError(NativePlaceMessages.LOCATION_NOT_FOUND)
        return village

    def list_for(self, user: User) -> list[UserNativePlace]:
        return self._places.list_by_user(user.id)

    def primary_village_id(self, user: User) -> UUID | None:
        primary = self._places.get_by_slot(user.id, NativePlaceSlot.PRIMARY)
        return primary.village_id if primary is not None else None

    def default_nearby_area(self, user: User) -> NearbyArea | None:
        village_id = self.primary_village_id(user)
        if village_id is None:
            return None
        point = self._villages.get_representative_point(village_id)
        if point is None:
            return None
        return NearbyArea(point[0], point[1], self._settings.nearby_radius_km(user))

    def set_primary(self, user: User, village_id: UUID) -> PrimaryNativePlaceResult:
        self._ensure_village_exists(village_id)
        secondary = self._places.get_by_slot(user.id, NativePlaceSlot.SECONDARY)
        if secondary is not None and secondary.village_id == village_id:
            raise BusinessRuleError(NativePlaceMessages.SAME_AS_SECONDARY)
        self._assign(user, NativePlaceSlot.PRIMARY, village_id)
        self._log(user, ActivityAction.NATIVE_PLACE_PRIMARY_SET, village_id)
        return PrimaryNativePlaceResult(
            places=self.list_for(user),
            secondary_eligibility=self._secondary_eligibility(village_id),
        )

    def set_secondary(self, user: User, village_id: UUID) -> list[UserNativePlace]:
        self._ensure_village_exists(village_id)
        primary = self._places.get_by_slot(user.id, NativePlaceSlot.PRIMARY)
        if primary is None:
            raise BusinessRuleError(NativePlaceMessages.PRIMARY_REQUIRED)
        if primary.village_id == village_id:
            raise BusinessRuleError(NativePlaceMessages.SAME_AS_PRIMARY)
        if not self._secondary_eligibility(primary.village_id).is_eligible:
            raise BusinessRuleError(NativePlaceMessages.SECONDARY_NOT_ELIGIBLE)
        self._assign(user, NativePlaceSlot.SECONDARY, village_id)
        self._log(user, ActivityAction.NATIVE_PLACE_SECONDARY_SET, village_id)
        return self.list_for(user)

    def remove_secondary(self, user: User) -> None:
        secondary = self._places.get_by_slot(user.id, NativePlaceSlot.SECONDARY)
        if secondary is None:
            raise NotFoundError(NativePlaceMessages.NO_SECONDARY)
        village_id = secondary.village_id
        self._places.delete(secondary)
        self._log(user, ActivityAction.NATIVE_PLACE_SECONDARY_REMOVED, village_id)

    def _secondary_eligibility(self, primary_village_id: UUID) -> SecondaryEligibility:
        point = self._villages.get_representative_point(primary_village_id)
        if point is None:
            raise NotFoundError(NativePlaceMessages.VILLAGE_NOT_FOUND)
        latitude, longitude = point
        radius_meters = SECONDARY_ELIGIBILITY_RADIUS_KM * METERS_PER_KM
        has_businesses = self._businesses.exists_listed_within(latitude, longitude, radius_meters)
        has_posts = self._posts.exists_visible_within(
            latitude, longitude, radius_meters, PostVisibilityScope()
        )
        return SecondaryEligibility(
            is_eligible=not has_businesses and not has_posts,
            radius_km=SECONDARY_ELIGIBILITY_RADIUS_KM,
            has_nearby_businesses=has_businesses,
            has_nearby_posts=has_posts,
        )

    def _fallback_districts(self, default_state_lgd_code: str) -> list[GisDistrict]:
        state = self._states.get_by_lgd_code(default_state_lgd_code)
        if state is None:
            return []
        districts, _ = self._districts.list_by_state(state.id, FALLBACK_DISTRICTS_PARAMS)
        return districts

    def _assign(self, user: User, slot: NativePlaceSlot, village_id: UUID) -> None:
        existing = self._places.get_by_slot(user.id, slot)
        if existing is None:
            self._places.add(UserNativePlace(user_id=user.id, village_id=village_id, slot=slot))
            return
        existing.village_id = village_id
        self._places.save(existing)

    def _ensure_village_exists(self, village_id: UUID) -> None:
        if self._villages.get_by_id(village_id) is None:
            raise NotFoundError(NativePlaceMessages.VILLAGE_NOT_FOUND)

    def _log(self, user: User, action: str, village_id: UUID) -> None:
        self._activity_logs.log(
            actor=user,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=village_id,
        )
