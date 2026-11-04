from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import OrderMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.direct_order import DirectOrderCreate
from app.schemas.order import OrderCancel, OrderListQuery, OrderRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.direct_order_service import DirectOrderService
from app.services.order_service import OrderService

router = APIRouter(prefix="/me/orders", tags=[ApiTag.ORDERS])
business_router = APIRouter(prefix="/businesses/{business_id}/orders", tags=[ApiTag.ORDERS])


@router.get("", response_model=SuccessResponse[Page[OrderRead]])
def list_my_orders(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[OrderListQuery, Query()],
) -> SuccessResponse[Page[OrderRead]]:
    orders, total = OrderService(db).list_mine(current_user, query.status, params)
    return SuccessResponse(
        message=OrderMessages.LIST_RETRIEVED,
        data=Page[OrderRead].create(items=orders, total=total, params=params),
    )


@router.get("/{order_id}", response_model=SuccessResponse[OrderRead])
def get_my_order(
    order_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[OrderRead]:
    order = OrderService(db).get_mine(order_id, current_user)
    return SuccessResponse(message=OrderMessages.RETRIEVED, data=order)


@router.post("/{order_id}/cancel", response_model=SuccessResponse[OrderRead])
def cancel_my_order(
    order_id: UUID,
    payload: OrderCancel,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = OrderService(db, registry).cancel_mine(order_id, payload, current_user)
    return SuccessResponse(message=OrderMessages.CANCELLED, data=order)


@business_router.post(
    "", response_model=SuccessResponse[OrderRead], status_code=status.HTTP_201_CREATED
)
def place_direct_order(
    business_id: UUID,
    payload: DirectOrderCreate,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = DirectOrderService(db, registry).place(business_id, payload, current_user)
    return SuccessResponse(message=OrderMessages.PLACED, data=order)
