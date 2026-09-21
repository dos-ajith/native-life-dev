from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gis_district import GisDistrict
from app.schemas.pagination import PaginationParams


class GisDistrictRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, district_id: UUID) -> GisDistrict | None:
        return self._db.get(GisDistrict, district_id)

    def list_by_state(
        self, state_id: UUID, params: PaginationParams
    ) -> tuple[list[GisDistrict], int]:
        where_clause = GisDistrict.state_id == state_id
        total = (
            self._db.scalar(select(func.count()).select_from(GisDistrict).where(where_clause))
            or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(GisDistrict)
            .where(where_clause)
            .order_by(GisDistrict.name)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total
