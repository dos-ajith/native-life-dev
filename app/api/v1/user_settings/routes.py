from fastapi import APIRouter

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import UserSettingsMessages
from app.schemas.response import SuccessResponse
from app.schemas.user_settings import (
    AISettingsRead,
    AISettingsUpdate,
    ContentSettingsRead,
    ContentSettingsUpdate,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    PrivacySettingsRead,
    PrivacySettingsUpdate,
    UserSettingsRead,
    UserSettingsUpdate,
)
from app.services.user_settings_service import UserSettingsService

router = APIRouter(prefix="/me/settings", tags=["user-settings"])


@router.get("", response_model=SuccessResponse[UserSettingsRead])
def get_my_settings(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[UserSettingsRead]:
    data = UserSettingsService(db).get_aggregate(current_user)
    return SuccessResponse(message=UserSettingsMessages.RETRIEVED, data=data)


@router.patch("", response_model=SuccessResponse[UserSettingsRead])
def update_my_settings(
    payload: UserSettingsUpdate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[UserSettingsRead]:
    data = UserSettingsService(db).update_aggregate(current_user, payload)
    return SuccessResponse(message=UserSettingsMessages.UPDATED, data=data)


@router.get("/ai", response_model=SuccessResponse[AISettingsRead])
def get_my_ai_settings(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[AISettingsRead]:
    data = UserSettingsService(db).get_ai(current_user)
    return SuccessResponse(message=UserSettingsMessages.AI_RETRIEVED, data=data)


@router.patch("/ai", response_model=SuccessResponse[AISettingsRead])
def update_my_ai_settings(
    payload: AISettingsUpdate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[AISettingsRead]:
    data = UserSettingsService(db).update_ai(current_user, payload)
    return SuccessResponse(message=UserSettingsMessages.AI_UPDATED, data=data)


@router.get("/notifications", response_model=SuccessResponse[NotificationSettingsRead])
def get_my_notification_settings(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[NotificationSettingsRead]:
    data = UserSettingsService(db).get_notifications(current_user)
    return SuccessResponse(message=UserSettingsMessages.NOTIFICATIONS_RETRIEVED, data=data)


@router.patch("/notifications", response_model=SuccessResponse[NotificationSettingsRead])
def update_my_notification_settings(
    payload: NotificationSettingsUpdate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[NotificationSettingsRead]:
    data = UserSettingsService(db).update_notifications(current_user, payload)
    return SuccessResponse(message=UserSettingsMessages.NOTIFICATIONS_UPDATED, data=data)


@router.get("/privacy", response_model=SuccessResponse[PrivacySettingsRead])
def get_my_privacy_settings(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[PrivacySettingsRead]:
    data = UserSettingsService(db).get_privacy(current_user)
    return SuccessResponse(message=UserSettingsMessages.PRIVACY_RETRIEVED, data=data)


@router.patch("/privacy", response_model=SuccessResponse[PrivacySettingsRead])
def update_my_privacy_settings(
    payload: PrivacySettingsUpdate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[PrivacySettingsRead]:
    data = UserSettingsService(db).update_privacy(current_user, payload)
    return SuccessResponse(message=UserSettingsMessages.PRIVACY_UPDATED, data=data)


@router.get("/content", response_model=SuccessResponse[ContentSettingsRead])
def get_my_content_settings(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[ContentSettingsRead]:
    data = UserSettingsService(db).get_content(current_user)
    return SuccessResponse(message=UserSettingsMessages.CONTENT_RETRIEVED, data=data)


@router.patch("/content", response_model=SuccessResponse[ContentSettingsRead])
def update_my_content_settings(
    payload: ContentSettingsUpdate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[ContentSettingsRead]:
    data = UserSettingsService(db).update_content(current_user, payload)
    return SuccessResponse(message=UserSettingsMessages.CONTENT_UPDATED, data=data)
