from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSessionDep, PaginationDep
from app.api.v1.native_places.permissions import (
    NativePlaceApproveDep,
    NativePlaceRejectDep,
    NativePlaceViewPendingDep,
)
from app.core.messages import NativePlaceMessages
from app.core.openapi_tags import ApiTag
from app.schemas.native_place import NativePlaceSuggestionRead, NativePlaceSuggestionReject
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.native_place_suggestion_service import NativePlaceSuggestionService

router = APIRouter(
    prefix="/admin/native-place-suggestions", tags=[ApiTag.ADMIN_NATIVE_PLACE_REVIEW]
)


@router.get("/pending", response_model=SuccessResponse[Page[NativePlaceSuggestionRead]])
def list_pending_suggestions(
    db: DbSessionDep, _: NativePlaceViewPendingDep, params: PaginationDep
) -> SuccessResponse[Page[NativePlaceSuggestionRead]]:
    items, total = NativePlaceSuggestionService(db).list_pending(params)
    page = Page[NativePlaceSuggestionRead].create(
        items=[NativePlaceSuggestionRead.from_suggestion(item) for item in items],
        total=total,
        params=params,
    )
    return SuccessResponse(message=NativePlaceMessages.PENDING_LIST_RETRIEVED, data=page)


@router.post("/{suggestion_id}/approve", response_model=SuccessResponse[NativePlaceSuggestionRead])
def approve_suggestion(
    suggestion_id: UUID, db: DbSessionDep, admin: NativePlaceApproveDep
) -> SuccessResponse[NativePlaceSuggestionRead]:
    suggestion = NativePlaceSuggestionService(db).approve(suggestion_id, admin)
    return SuccessResponse(
        message=NativePlaceMessages.APPROVED,
        data=NativePlaceSuggestionRead.from_suggestion(suggestion),
    )


@router.post("/{suggestion_id}/reject", response_model=SuccessResponse[NativePlaceSuggestionRead])
def reject_suggestion(
    suggestion_id: UUID,
    payload: NativePlaceSuggestionReject,
    db: DbSessionDep,
    admin: NativePlaceRejectDep,
) -> SuccessResponse[NativePlaceSuggestionRead]:
    suggestion = NativePlaceSuggestionService(db).reject(suggestion_id, admin, payload.review_note)
    return SuccessResponse(
        message=NativePlaceMessages.REJECTED,
        data=NativePlaceSuggestionRead.from_suggestion(suggestion),
    )
