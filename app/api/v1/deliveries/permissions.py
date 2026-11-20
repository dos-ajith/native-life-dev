from typing import Annotated

from fastapi import Depends

from app.api.deps import CurrentActiveUserDep
from app.core.exceptions import AuthorizationError
from app.core.messages import DeliveryMessages, DeliveryTeamMessages
from app.models.user import User
from app.services.promoter_team_scope import is_delivery_team_member, is_verified_promoter


def require_verified_promoter(user: CurrentActiveUserDep) -> User:
    if not is_verified_promoter(user):
        raise AuthorizationError(DeliveryMessages.PROMOTER_ONLY)
    return user


VerifiedPromoterDep = Annotated[User, Depends(require_verified_promoter)]


def require_delivery_team_member(user: CurrentActiveUserDep) -> User:
    if not is_delivery_team_member(user):
        raise AuthorizationError(DeliveryTeamMessages.COURIER_ONLY)
    return user


DeliveryTeamMemberDep = Annotated[User, Depends(require_delivery_team_member)]


def require_route_operator(user: CurrentActiveUserDep) -> User:
    if not (is_verified_promoter(user) or is_delivery_team_member(user)):
        raise AuthorizationError(DeliveryMessages.TRACKING_NOT_ALLOWED)
    return user


RouteOperatorDep = Annotated[User, Depends(require_route_operator)]
