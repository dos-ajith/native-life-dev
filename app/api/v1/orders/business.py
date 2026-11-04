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
from app.services.business_order_service import BusinessOrderService

router = APIRouter(prefix="/me/businesses/{business_id}/orders", tags=[ApiTag.BUSINESS_ORDERS])


@router.get("", response_model=SuccessResponse[Page[OrderRead]])
def list_business_orders(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[OrderListQuery, Query()],
) -> SuccessResponse[Page[OrderRead]]:
    orders, total = BusinessOrderService(db).list_orders(
        business_id, query.status, params, current_user
    )
    return SuccessResponse(
        message=OrderMessages.LIST_RETRIEVED,
        data=Page[OrderRead].create(items=orders, total=total, params=params),
    )


@router.get("/{order_id}", response_model=SuccessResponse[OrderRead])
def get_business_order(
    business_id: UUID, order_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[OrderRead]:
    order = BusinessOrderService(db).get(business_id, order_id, current_user)
    return SuccessResponse(message=OrderMessages.RETRIEVED, data=order)


@router.post("/{order_id}/status", response_model=SuccessResponse[OrderRead])
def update_business_order_status(
    business_id: UUID,
    order_id: UUID,
    payload: OrderStatusUpdate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = BusinessOrderService(db).update_status(business_id, order_id, payload, current_user)
    return SuccessResponse(message=OrderMessages.STATUS_UPDATED, data=order)


@router.post("/{order_id}/cancel", response_model=SuccessResponse[OrderRead])
def cancel_business_order(
    business_id: UUID,
    order_id: UUID,
    payload: OrderCancel,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = BusinessOrderService(db, registry).cancel(business_id, order_id, payload, current_user)
    return SuccessResponse(message=OrderMessages.CANCELLED, data=order)
