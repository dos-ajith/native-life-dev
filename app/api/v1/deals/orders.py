from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.deal_order import DealOrderCreate
from app.schemas.order import OrderRead
from app.schemas.response import SuccessResponse
from app.services.deal_order_service import DealOrderService

router = APIRouter(prefix="/deals/{deal_id}/orders", tags=[ApiTag.DEAL_ORDERS])


@router.post("", response_model=SuccessResponse[OrderRead], status_code=status.HTTP_201_CREATED)
def place_deal_order(
    deal_id: UUID,
    payload: DealOrderCreate,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = DealOrderService(db, registry).place(deal_id, payload, current_user)
    return SuccessResponse(message=DealMessages.ORDER_PLACED, data=order)
