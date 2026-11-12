from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import CartMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.cart import (
    CartCheckout,
    CartItemAdd,
    CartItemUpdate,
    CartProductAdd,
    CartRead,
)
from app.schemas.deal_order import OrderDetails
from app.schemas.order import OrderRead
from app.schemas.response import SuccessResponse
from app.services.cart_service import CartService

router = APIRouter(prefix="/me/cart", tags=[ApiTag.CART])


@router.get("", response_model=SuccessResponse[CartRead])
def get_my_cart(
    db: DbSessionDep, registry: PluginRegistryDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).get(current_user)
    return SuccessResponse(message=CartMessages.RETRIEVED, data=cart)


@router.post(
    "/items", response_model=SuccessResponse[CartRead], status_code=status.HTTP_201_CREATED
)
def add_cart_item(
    payload: CartItemAdd,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).add_item(payload, current_user)
    return SuccessResponse(message=CartMessages.ITEM_ADDED, data=cart)


@router.patch("/items/{cart_item_id}", response_model=SuccessResponse[CartRead])
def update_cart_item(
    cart_item_id: UUID,
    payload: CartItemUpdate,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).update_item(cart_item_id, payload, current_user)
    return SuccessResponse(message=CartMessages.ITEM_UPDATED, data=cart)


@router.delete("/items/{cart_item_id}", response_model=SuccessResponse[CartRead])
def remove_cart_item(
    cart_item_id: UUID,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).remove_item(cart_item_id, current_user)
    return SuccessResponse(message=CartMessages.ITEM_REMOVED, data=cart)


@router.delete("/deals/{deal_id}", response_model=SuccessResponse[CartRead])
def remove_cart_deal(
    deal_id: UUID,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).remove_deal(deal_id, current_user)
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


@router.post(
    "/products", response_model=SuccessResponse[CartRead], status_code=status.HTTP_201_CREATED
)
def add_cart_product(
    payload: CartProductAdd,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).add_product(payload, current_user)
    return SuccessResponse(message=CartMessages.PRODUCT_ADDED, data=cart)


@router.patch("/products/{cart_item_id}", response_model=SuccessResponse[CartRead])
def update_cart_product(
    cart_item_id: UUID,
    payload: CartItemUpdate,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).update_product(cart_item_id, payload, current_user)
    return SuccessResponse(message=CartMessages.PRODUCT_UPDATED, data=cart)


@router.delete("/products/{cart_item_id}", response_model=SuccessResponse[CartRead])
def remove_cart_product(
    cart_item_id: UUID,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).remove_product(cart_item_id, current_user)
    return SuccessResponse(message=CartMessages.PRODUCT_REMOVED, data=cart)


@router.delete("/businesses/{business_id}", response_model=SuccessResponse[CartRead])
def remove_cart_business(
    business_id: UUID,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CartRead]:
    cart = CartService(db, registry).remove_business(business_id, current_user)
    return SuccessResponse(message=CartMessages.BUSINESS_REMOVED, data=cart)


@router.post(
    "/products/checkout",
    response_model=SuccessResponse[list[OrderRead]],
    status_code=status.HTTP_201_CREATED,
)
def checkout_all_product_carts(
    payload: OrderDetails,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[list[OrderRead]]:
    orders = CartService(db, registry).checkout_all_businesses(payload, current_user)
    return SuccessResponse(message=CartMessages.CHECKED_OUT_ALL, data=orders)


@router.post(
    "/businesses/{business_id}/checkout",
    response_model=SuccessResponse[OrderRead],
    status_code=status.HTTP_201_CREATED,
)
def checkout_business_cart(
    business_id: UUID,
    payload: OrderDetails,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[OrderRead]:
    order = CartService(db, registry).checkout_business(business_id, payload, current_user)
    return SuccessResponse(message=CartMessages.CHECKED_OUT, data=order)
