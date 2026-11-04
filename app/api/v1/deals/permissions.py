from typing import Annotated

from fastapi import Depends

from app.api.deps import CurrentActiveUserDep, DbSessionDep, require_permission
from app.core.exceptions import AuthorizationError
from app.core.messages import DealMessages, DeliveryMessages
from app.core.permissions import PermissionName
from app.models.user import User
from app.services.deal_eligibility_service import DealEligibilityService
from app.services.delivery_access_service import DeliveryAccessService

DealCreateDep = Annotated[User, Depends(require_permission(PermissionName.DEAL_CREATE))]


def require_deal_acceptor(user: CurrentActiveUserDep, db: DbSessionDep) -> User:
    if not DealEligibilityService(db).holds_accepting_role(user):
        raise AuthorizationError(DealMessages.NOT_ACCEPTOR)
    return user


DealAcceptorDep = Annotated[User, Depends(require_deal_acceptor)]


def require_delivery_settings_role(user: CurrentActiveUserDep, db: DbSessionDep) -> User:
    if not DeliveryAccessService(db).holds_role(user):
        raise AuthorizationError(DeliveryMessages.NOT_ALLOWED)
    return user


DeliverySettingsManagerDep = Annotated[User, Depends(require_delivery_settings_role)]
