from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import CartMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.cart import CartCheckout, CartItemAdd, CartItemUpdate, CartRead
from app.schemas.order import OrderRead
from app.schemas.response import SuccessResponse
from app.services.cart_service import CartService

router = APIRouter(prefix="/me/cart", tags=[ApiTag.CART])


@router.get("", response_model=SuccessResponse[CartRead])
def get_my_cart(db: DbSessionDep, current_user: CurrentActiveUserDep) -> SuccessResponse[CartRead]:
    return SuccessResponse(message=CartMessages.RETRIEVED, data=CartService(db).get(current_user))


@router.post(
    "/items", response_model=SuccessResponse[CartRead], status_code=status.HTTP_201_CREATED
)
def add_cart_item(
    payload: CartItemAdd, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CartRead]:
    cart = CartService(db).add_item(payload, current_user)
    return SuccessResponse(message=CartMessages.ITEM_ADDED, data=cart)


@router.patch("/items/{cart_item_id}", response_model=SuccessResponse[CartRead])
def update_cart_item(
    cart_item_id: UUID,
    payload: CartItemUpdate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db).update_item(cart_item_id, payload, current_user)
    return SuccessResponse(message=CartMessages.ITEM_UPDATED, data=cart)


@router.delete("/items/{cart_item_id}", response_model=SuccessResponse[CartRead])
def remove_cart_item(
    cart_item_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CartRead]:
    cart = CartService(db).remove_item(cart_item_id, current_user)
    return SuccessResponse(message=CartMessages.ITEM_REMOVED, data=cart)


@router.delete("/deals/{deal_id}", response_model=SuccessResponse[CartRead])
def remove_cart_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CartRead]:
    cart = CartService(db).remove_deal(deal_id, current_user)
    return SuccessResponse(message=CartMessages.DEAL_REMOVED, data=cart)


@router.post(
    "/checkout", response_model=SuccessResponse[OrderRead], status_code=status.HTTP_201_CREATED
)
def checkout_cart(
    payload: CartCheckout,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = CartService(db, registry).checkout(payload, current_user)
    return SuccessResponse(message=CartMessages.CHECKED_OUT, data=order)
