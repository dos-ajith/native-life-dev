from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import UserBlockMessages, UserMessages
from app.models.user import User
from app.repositories.user_block_repository import UserBlockRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "user"


class UserBlockService:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)
        self._blocks = UserBlockRepository(db)
        self._activity_logs = ActivityLogService(db)

    def block(self, target_id: UUID, actor: User) -> None:
        if target_id == actor.id:
            raise BusinessRuleError(UserBlockMessages.CANNOT_BLOCK_SELF)
        if self._users.get_by_id(target_id) is None:
            raise NotFoundError(UserMessages.NOT_FOUND)
        if not self._blocks.create(actor.id, target_id):
            raise BusinessRuleError(UserBlockMessages.ALREADY_BLOCKED)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_BLOCKED,
            entity_type=ENTITY_TYPE,
            entity_id=target_id,
        )

    def unblock(self, target_id: UUID, actor: User) -> None:
        if not self._blocks.delete(actor.id, target_id):
            raise BusinessRuleError(UserBlockMessages.NOT_BLOCKED)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_UNBLOCKED,
            entity_type=ENTITY_TYPE,
            entity_id=target_id,
        )

    def list_blocked(self, actor: User, params: PaginationParams) -> tuple[list[User], int]:
        return self._blocks.list_blocked(actor.id, params)
