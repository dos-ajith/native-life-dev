from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import GeographyMessages
from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.repositories.gis_district_repository import GisDistrictRepository
from app.repositories.gis_state_repository import GisStateRepository
from app.repositories.gis_taluk_repository import GisTalukRepository
from app.schemas.pagination import PaginationParams


class GeographyService:
    def __init__(self, db: Session) -> None:
        self._states = GisStateRepository(db)
        self._districts = GisDistrictRepository(db)
        self._taluks = GisTalukRepository(db)

    def list_states(self, params: PaginationParams) -> tuple[list[GisState], int]:
        return self._states.list(params)

    def list_districts(
        self, state_id: UUID, params: PaginationParams
    ) -> tuple[list[GisDistrict], int]:
        if self._states.get_by_id(state_id) is None:
            raise NotFoundError(GeographyMessages.STATE_NOT_FOUND)
        return self._districts.list_by_state(state_id, params)

    def list_taluks(
        self, district_id: UUID, params: PaginationParams
    ) -> tuple[list[GisTaluk], int]:
        if self._districts.get_by_id(district_id) is None:
            raise NotFoundError(GeographyMessages.DISTRICT_NOT_FOUND)
        return self._taluks.list_by_district(district_id, params)

    def reverse_geocode(self, latitude: float, longitude: float) -> GisTaluk:
        taluk = self._taluks.find_containing_point(latitude, longitude)
        if taluk is None:
            raise NotFoundError(GeographyMessages.LOCATION_NOT_FOUND)
        return taluk

    def search_districts(self, query: str, limit: int) -> list[GisDistrict]:
        return self._districts.search_by_name(query, limit)
