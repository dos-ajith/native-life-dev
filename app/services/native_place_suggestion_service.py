from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import NativePlaceMessages
from app.core.timezone import app_now
from app.models.native_place_suggestion import NativePlaceSuggestion, NativePlaceSuggestionStatus
from app.models.user import User
from app.repositories.gis_district_repository import GisDistrictRepository
from app.repositories.native_place_suggestion_repository import NativePlaceSuggestionRepository
from app.schemas.native_place import NativePlaceSuggestionCreate
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "native_place_suggestion"


class NativePlaceSuggestionService:
    def __init__(self, db: Session) -> None:
        self._districts = GisDistrictRepository(db)
        self._suggestions = NativePlaceSuggestionRepository(db)
        self._activity_logs = ActivityLogService(db)

    def suggest(self, payload: NativePlaceSuggestionCreate, actor: User) -> NativePlaceSuggestion:
        if self._districts.get_by_id(payload.district_id) is None:
            raise NotFoundError(NativePlaceMessages.DISTRICT_NOT_FOUND)
        suggestion = self._suggestions.add(
            NativePlaceSuggestion(
                name=payload.name,
                district_id=payload.district_id,
                status=NativePlaceSuggestionStatus.PENDING,
                created_by=actor.id,
            )
        )
        self._log(actor, ActivityAction.NATIVE_PLACE_SUGGESTED, suggestion)
        return suggestion

    def list_pending(self, params: PaginationParams) -> tuple[list[NativePlaceSuggestion], int]:
        return self._suggestions.list_pending(params)

    def approve(self, suggestion_id: UUID, admin: User) -> NativePlaceSuggestion:
        suggestion = self._review(suggestion_id, admin, NativePlaceSuggestionStatus.APPROVED, None)
        self._log(admin, ActivityAction.NATIVE_PLACE_APPROVED, suggestion)
        return suggestion

    def reject(self, suggestion_id: UUID, admin: User, review_note: str) -> NativePlaceSuggestion:
        suggestion = self._review(
            suggestion_id, admin, NativePlaceSuggestionStatus.REJECTED, review_note
        )
        self._log(admin, ActivityAction.NATIVE_PLACE_REJECTED, suggestion)
        return suggestion

    def _review(
        self,
        suggestion_id: UUID,
        admin: User,
        status: NativePlaceSuggestionStatus,
        review_note: str | None,
    ) -> NativePlaceSuggestion:
        suggestion = self._suggestions.get_by_id(suggestion_id)
        if suggestion is None:
            raise NotFoundError(NativePlaceMessages.SUGGESTION_NOT_FOUND)
        if suggestion.status != NativePlaceSuggestionStatus.PENDING:
            raise BusinessRuleError(NativePlaceMessages.NOT_PENDING)
        suggestion.status = status
        suggestion.reviewed_by = admin.id
        suggestion.reviewed_at = app_now()
        suggestion.review_note = review_note
        return self._suggestions.save(suggestion)

    def _log(self, actor: User, action: str, suggestion: NativePlaceSuggestion) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=suggestion.id,
            metadata={"name": suggestion.name},
        )
