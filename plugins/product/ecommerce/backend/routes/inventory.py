from typing import Annotated
from uuid import UUID

from fastapi import APIRouter

from app.plugins.sdk import DbSessionDep, Page, PaginationDep, SuccessResponse

from ..messages import EcommerceMessages
from ..schemas.inventory import (
    StockAdjustmentCreate,
    StockLevelRead,
    StockMovementRead,
    StockThresholdUpdate,
)
from ..schemas.product import ProductStockRead
from ..services.inventory_service import InventoryService
from .blank_values import BlankAsNone
from .dependencies import BusinessDep, InventoryManagerDep, InventoryViewerDep

router = APIRouter()


@router.get(
    "/businesses/{business_id}/inventory", response_model=SuccessResponse[Page[StockLevelRead]]
)
def list_stock(
    _: InventoryViewerDep, business: BusinessDep, db: DbSessionDep, params: PaginationDep
) -> SuccessResponse[Page[StockLevelRead]]:
    return SuccessResponse(
        message=EcommerceMessages.STOCK_LIST_RETRIEVED,
        data=InventoryService(db).list_stock(business.id, params, low_only=False),
    )


@router.get(
    "/businesses/{business_id}/inventory/low-stock",
    response_model=SuccessResponse[Page[StockLevelRead]],
)
def list_low_stock(
    _: InventoryViewerDep, business: BusinessDep, db: DbSessionDep, params: PaginationDep
) -> SuccessResponse[Page[StockLevelRead]]:
    return SuccessResponse(
        message=EcommerceMessages.LOW_STOCK_RETRIEVED,
        data=InventoryService(db).list_stock(business.id, params, low_only=True),
    )


@router.get(
    "/businesses/{business_id}/inventory/movements",
    response_model=SuccessResponse[Page[StockMovementRead]],
)
def list_business_stock_movements(
    _: InventoryViewerDep,
    business: BusinessDep,
    db: DbSessionDep,
    params: PaginationDep,
    product_id: Annotated[UUID | None, BlankAsNone] = None,
) -> SuccessResponse[Page[StockMovementRead]]:
    return SuccessResponse(
        message=EcommerceMessages.STOCK_MOVEMENTS_RETRIEVED,
        data=InventoryService(db).movements(business.id, product_id, params),
    )


@router.get(
    "/businesses/{business_id}/products/{product_id}/stock",
    response_model=SuccessResponse[ProductStockRead],
)
def get_stock(
    _: InventoryViewerDep, business: BusinessDep, db: DbSessionDep, product_id: UUID
) -> SuccessResponse[ProductStockRead]:
    return SuccessResponse(
        message=EcommerceMessages.STOCK_RETRIEVED,
        data=InventoryService(db).get_stock(business.id, product_id),
    )


@router.post(
    "/businesses/{business_id}/products/{product_id}/stock-adjustments",
    response_model=SuccessResponse[ProductStockRead],
)
def adjust_stock(
    actor: InventoryManagerDep,
    business: BusinessDep,
    db: DbSessionDep,
    product_id: UUID,
    payload: StockAdjustmentCreate,
) -> SuccessResponse[ProductStockRead]:
    return SuccessResponse(
        message=EcommerceMessages.STOCK_ADJUSTED,
        data=InventoryService(db).adjust(business.id, product_id, payload, actor),
    )


@router.put(
    "/businesses/{business_id}/products/{product_id}/stock/threshold",
    response_model=SuccessResponse[ProductStockRead],
)
def update_stock_threshold(
    actor: InventoryManagerDep,
    business: BusinessDep,
    db: DbSessionDep,
    product_id: UUID,
    payload: StockThresholdUpdate,
) -> SuccessResponse[ProductStockRead]:
    return SuccessResponse(
        message=EcommerceMessages.STOCK_THRESHOLD_UPDATED,
        data=InventoryService(db).set_threshold(business.id, product_id, payload, actor),
    )


@router.get(
    "/businesses/{business_id}/products/{product_id}/stock-movements",
    response_model=SuccessResponse[Page[StockMovementRead]],
)
def list_stock_movements(
    _: InventoryViewerDep,
    business: BusinessDep,
    db: DbSessionDep,
    product_id: UUID,
    params: PaginationDep,
) -> SuccessResponse[Page[StockMovementRead]]:
    return SuccessResponse(
        message=EcommerceMessages.STOCK_MOVEMENTS_RETRIEVED,
        data=InventoryService(db).movements(business.id, product_id, params),
    )
