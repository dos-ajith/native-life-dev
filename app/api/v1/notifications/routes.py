from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import NotificationMessages
from app.schemas.notification import NotificationRead, NotificationUnreadCountRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


@router.get("", response_model=SuccessResponse[Page[NotificationRead]])
def list_notifications(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    unread_only: bool = False,
) -> SuccessResponse[Page[NotificationRead]]:
    items, total = NotificationService(db).list_notifications(current_user, params, unread_only)
    page = Page[NotificationRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=NotificationMessages.LIST_RETRIEVED, data=page)


@router.get("/unread-count", response_model=SuccessResponse[NotificationUnreadCountRead])
def get_unread_count(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[NotificationUnreadCountRead]:
    unread_count = NotificationService(db).get_unread_count(current_user)
    return SuccessResponse(
        message=NotificationMessages.UNREAD_COUNT_RETRIEVED,
        data=NotificationUnreadCountRead(unread_count=unread_count),
    )


@router.patch("/{notification_id}/read", response_model=SuccessResponse[NotificationRead])
def mark_notification_read(
    notification_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[NotificationRead]:
    data = NotificationService(db).mark_notification_read(current_user, notification_id)
    return SuccessResponse(message=NotificationMessages.MARKED_READ, data=data)


@router.post("/read-all", response_model=SuccessResponse[None])
def mark_all_notifications_read(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    NotificationService(db).mark_all_notifications_read(current_user)
    return SuccessResponse(message=NotificationMessages.ALL_MARKED_READ, data=None)
