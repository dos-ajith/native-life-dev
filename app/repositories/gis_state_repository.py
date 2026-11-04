from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gis_state import GisState
from app.schemas.pagination import PaginationParams


class GisStateRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, state_id: UUID) -> GisState | None:
        return self._db.get(GisState, state_id)

    def get_by_lgd_code(self, lgd_code: str) -> GisState | None:
        return self._db.scalar(select(GisState).where(GisState.lgd_code == lgd_code))

    def list(self, params: PaginationParams) -> tuple[list[GisState], int]:
        total = self._db.scalar(select(func.count()).select_from(GisState)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(GisState).order_by(GisState.name).offset(offset).limit(params.page_size)
        ).all()
        return list(items), total
