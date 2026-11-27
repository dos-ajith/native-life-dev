from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.messages import UserMessages
from app.models.user_settings_enums import ProfileVisibility
from app.repositories.user_block_repository import UserBlockRepository
from app.repositories.user_follow_repository import UserFollowRepository
from app.repositories.user_privacy_settings_repository import UserPrivacySettingsRepository


class ProfileAccessService:
    def __init__(self, db: Session) -> None:
        self._privacy = UserPrivacySettingsRepository(db)
        self._follows = UserFollowRepository(db)
        self._blocks = UserBlockRepository(db)

    def is_private(self, user_id: UUID) -> bool:
        settings = self._privacy.get_by_user_id(user_id)
        if settings is None:
            return False
        return settings.profile_visibility == ProfileVisibility.PRIVATE

    def ensure_not_blocked(self, viewer_id: UUID, user_id: UUID) -> None:
        if viewer_id != user_id and self._blocks.exists(user_id, viewer_id):
            raise NotFoundError(UserMessages.NOT_FOUND)

    def can_view_content(self, viewer_id: UUID, user_id: UUID, is_private: bool) -> bool:
        if viewer_id == user_id or not is_private:
            return True
        return self._follows.exists(viewer_id, user_id)

    def ensure_can_view_content(self, viewer_id: UUID, user_id: UUID) -> None:
        self.ensure_not_blocked(viewer_id, user_id)
        if not self.can_view_content(viewer_id, user_id, self.is_private(user_id)):
            raise AuthorizationError(UserMessages.PRIVATE_ACCOUNT)
