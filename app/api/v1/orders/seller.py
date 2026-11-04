from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import OrderMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.order import OrderCancel, OrderListQuery, OrderRead, OrderStatusUpdate
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.seller_order_service import SellerOrderService

router = APIRouter(prefix="/me/deal-orders", tags=[ApiTag.SELLER_ORDERS])


@router.get("", response_model=SuccessResponse[Page[OrderRead]])
def list_my_deal_orders(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[OrderListQuery, Query()],
) -> SuccessResponse[Page[OrderRead]]:
    orders, total = SellerOrderService(db).list_orders(query.status, params, current_user)
    return SuccessResponse(
        message=OrderMessages.LIST_RETRIEVED,
        data=Page[OrderRead].create(items=orders, total=total, params=params),
    )


@router.get("/{order_id}", response_model=SuccessResponse[OrderRead])
def get_my_deal_order(
    order_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[OrderRead]:
    return SuccessResponse(
        message=OrderMessages.RETRIEVED, data=SellerOrderService(db).get(order_id, current_user)
    )


@router.post("/{order_id}/status", response_model=SuccessResponse[OrderRead])
def update_my_deal_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = SellerOrderService(db).update_status(order_id, payload, current_user)
    return SuccessResponse(message=OrderMessages.STATUS_UPDATED, data=order)


@router.post("/{order_id}/cancel", response_model=SuccessResponse[OrderRead])
def cancel_my_deal_order(
    order_id: UUID,
    payload: OrderCancel,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = SellerOrderService(db, registry).cancel(order_id, payload, current_user)
    return SuccessResponse(message=OrderMessages.CANCELLED, data=order)
