from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError, BusinessRuleError
from app.core.messages import DeliveryTeamMessages
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.delivery_team import DeliveryTeamMemberCreate
from app.schemas.user import UserCreate
from app.services.authorization_service import is_admin
from app.services.promoter_team_scope import PromoterTeamScope, is_verified_promoter
from app.services.user_service import UserService


class DeliveryTeamService:
    def __init__(self, db: Session) -> None:
        self._users = UserService(db)
        self._user_repository = UserRepository(db)
        self._scope = PromoterTeamScope(db)

    def create(
        self,
        payload: DeliveryTeamMemberCreate,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        promoter = self._owning_promoter(payload, actor)
        account = UserCreate.model_validate(payload.model_dump(exclude={"promoter_id"}))
        return self._users.create_delivery_team_member(
            account, promoter.id, actor, ip_address, user_agent
        )

    def list_team(self, actor: User) -> list[User]:
        return self._scope.team(actor.id)

    def list_promoters(self) -> list[User]:
        return list(self._user_repository.list_verified_promoters())

    def _owning_promoter(self, payload: DeliveryTeamMemberCreate, actor: User) -> User:
        if is_admin(actor):
            if payload.promoter_id is None:
                raise BusinessRuleError(DeliveryTeamMessages.PROMOTER_REQUIRED)
            return self._scope.verified_promoter(payload.promoter_id)
        if not is_verified_promoter(actor):
            raise AuthorizationError(DeliveryTeamMessages.NOT_ALLOWED)
        return actor
