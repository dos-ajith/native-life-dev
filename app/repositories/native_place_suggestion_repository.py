from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.native_place_suggestion import NativePlaceSuggestion, NativePlaceSuggestionStatus
from app.schemas.pagination import PaginationParams


class NativePlaceSuggestionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, suggestion_id: UUID) -> NativePlaceSuggestion | None:
        return self._db.get(NativePlaceSuggestion, suggestion_id)

    def list_pending(self, params: PaginationParams) -> tuple[list[NativePlaceSuggestion], int]:
        conditions = [NativePlaceSuggestion.status == NativePlaceSuggestionStatus.PENDING]
        total = (
            self._db.scalar(
                select(func.count()).select_from(NativePlaceSuggestion).where(*conditions)
            )
            or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(NativePlaceSuggestion)
            .options(
                joinedload(NativePlaceSuggestion.district),
                joinedload(NativePlaceSuggestion.submitter),
            )
            .where(*conditions)
            .order_by(NativePlaceSuggestion.created_at.asc(), NativePlaceSuggestion.id.asc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def add(self, suggestion: NativePlaceSuggestion) -> NativePlaceSuggestion:
        self._db.add(suggestion)
        self._db.commit()
        self._db.refresh(suggestion)
        return suggestion

    def save(self, suggestion: NativePlaceSuggestion) -> NativePlaceSuggestion:
        self._db.commit()
        self._db.refresh(suggestion)
        return suggestion
