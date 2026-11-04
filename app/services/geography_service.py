from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import GeographyMessages
from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.repositories.gis_district_repository import GisDistrictRepository
from app.repositories.gis_state_repository import GisStateRepository
from app.repositories.gis_taluk_repository import GisTalukRepository
from app.repositories.gis_village_repository import GisVillageRepository
from app.schemas.pagination import PaginationParams


class GeographyService:
    def __init__(self, db: Session) -> None:
        self._states = GisStateRepository(db)
        self._districts = GisDistrictRepository(db)
        self._taluks = GisTalukRepository(db)
        self._villages = GisVillageRepository(db)

    def list_states(self, params: PaginationParams) -> tuple[list[GisState], int]:
        return self._states.list(params)

    def list_districts(
        self, state_id: UUID, params: PaginationParams
    ) -> tuple[list[GisDistrict], int]:
        if self._states.get_by_id(state_id) is None:
            raise NotFoundError(GeographyMessages.STATE_NOT_FOUND)
        return self._districts.list_by_state(state_id, params)

    def list_districts_with_default_state(
        self, state_id: UUID | None, default_state_lgd_code: str, params: PaginationParams
    ) -> tuple[list[GisDistrict], int]:
        if state_id is not None:
            return self.list_districts(state_id, params)
        default_state = self._states.get_by_lgd_code(default_state_lgd_code)
        if default_state is None:
            raise NotFoundError(GeographyMessages.STATE_NOT_FOUND)
        return self._districts.list_by_state(default_state.id, params)

    def list_taluks(
        self, district_id: UUID, params: PaginationParams
    ) -> tuple[list[GisTaluk], int]:
        if self._districts.get_by_id(district_id) is None:
            raise NotFoundError(GeographyMessages.DISTRICT_NOT_FOUND)
        return self._taluks.list_by_district(district_id, params)

    def list_villages(
        self, taluk_id: UUID, params: PaginationParams
    ) -> tuple[list[GisVillage], int]:
        if self._taluks.get_by_id(taluk_id) is None:
            raise NotFoundError(GeographyMessages.TALUK_NOT_FOUND)
        return self._villages.list_by_taluk(taluk_id, params)

    def reverse_geocode(self, latitude: float, longitude: float) -> GisTaluk:
        taluk = self._taluks.find_containing_point(latitude, longitude)
        if taluk is None:
            raise NotFoundError(GeographyMessages.LOCATION_NOT_FOUND)
        return taluk

    def format_location_name(self, taluk: GisTaluk) -> str:
        return f"{taluk.name}, {taluk.district.name}, {taluk.district.state.name}"

    def suggest_addresses(self, query: str, limit: int) -> list[str]:
        taluks = self._taluks.search_by_name(query.strip(), limit)
        return [self.format_location_name(taluk) for taluk in taluks]

    def search_districts(self, query: str, limit: int) -> list[GisDistrict]:
        return self._districts.search_by_name(query, limit)
