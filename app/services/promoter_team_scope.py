from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import DeliveryTeamMessages
from app.core.permissions import RoleSlug
from app.models.user import User, UserStatus
from app.repositories.user_repository import UserRepository


def is_verified_promoter(user: User) -> bool:
    return any(role.slug == RoleSlug.PROMOTER for role in user.approved_roles)


def is_delivery_team_member(user: User) -> bool:
    return any(role.slug == RoleSlug.DELIVERY_TEAM for role in user.roles)


class PromoterTeamScope:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)

    def verified_promoter(self, user_id: UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE or not is_verified_promoter(user):
            raise BusinessRuleError(DeliveryTeamMessages.PROMOTER_INVALID)
        return user

    def team_member(self, promoter_id: UUID, member_id: UUID) -> User:
        member = self._users.get_by_id(member_id)
        if (
            member is None
            or member.promoter_id != promoter_id
            or not is_delivery_team_member(member)
        ):
            raise NotFoundError(DeliveryTeamMessages.MEMBER_NOT_FOUND)
        return member

    def team(self, promoter_id: UUID) -> list[User]:
        return [
            member
            for member in self._users.list_by_promoter(promoter_id)
            if is_delivery_team_member(member)
        ]
