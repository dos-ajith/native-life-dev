from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gis_taluk import GisTaluk
from app.schemas.pagination import PaginationParams


class GisTalukRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_district(
        self, district_id: UUID, params: PaginationParams
    ) -> tuple[list[GisTaluk], int]:
        where_clause = GisTaluk.district_id == district_id
        total = (
            self._db.scalar(select(func.count()).select_from(GisTaluk).where(where_clause)) or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(GisTaluk)
            .where(where_clause)
            .order_by(GisTaluk.name)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total
