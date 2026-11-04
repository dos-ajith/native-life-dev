from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile

from app.plugins.sdk import DbSessionDep, Page, PaginationDep, SuccessResponse

from ..messages import EcommerceMessages
from ..schemas.product import (
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCreate,
    ProductImageRead,
    ProductRead,
    ProductUpdate,
)
from ..services.product_service import ProductService
from .blank_values import BlankAsNone
from .dependencies import BusinessDep, ProductManagerDep, ProductViewerDep

CREATED = 201
SEARCH_MAX_LENGTH = 100

router = APIRouter()


@router.get("/businesses/{business_id}/products", response_model=SuccessResponse[Page[ProductRead]])
def list_products(
    _: ProductViewerDep,
    business: BusinessDep,
    db: DbSessionDep,
    params: PaginationDep,
    is_active: Annotated[bool | None, BlankAsNone] = None,
    category_id: Annotated[UUID | None, BlankAsNone] = None,
    q: Annotated[str | None, Query(max_length=SEARCH_MAX_LENGTH)] = None,
) -> SuccessResponse[Page[ProductRead]]:
    return SuccessResponse(
        message=EcommerceMessages.PRODUCTS_RETRIEVED,
        data=ProductService(db).list_products(business.id, params, is_active, category_id, q),
    )


@router.post(
    "/businesses/{business_id}/products",
    response_model=SuccessResponse[ProductRead],
    status_code=CREATED,
)
def create_product(
    actor: ProductManagerDep,
    business: BusinessDep,
    db: DbSessionDep,
    name: Annotated[str, Form()],
    sku: Annotated[str, Form()],
    selling_price: Annotated[Decimal, Form()],
    category_id: Annotated[UUID, Form()],
    original_price: Annotated[Decimal | None, Form(), BlankAsNone] = None,
    description: Annotated[str | None, Form()] = None,
    is_active: Annotated[bool, Form()] = True,
    is_bulk_promotable: Annotated[bool, Form()] = False,
    is_individually_promotable: Annotated[bool, Form()] = False,
    quantity: Annotated[int, Form()] = 0,
    low_stock_threshold: Annotated[int | None, Form(), BlankAsNone] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> SuccessResponse[ProductRead]:
    payload = ProductCreate(
        name=name,
        description=description,
        sku=sku,
        selling_price=selling_price,
        original_price=original_price,
        category_id=category_id,
        is_active=is_active,
        is_bulk_promotable=is_bulk_promotable,
        is_individually_promotable=is_individually_promotable,
        quantity=quantity,
        low_stock_threshold=low_stock_threshold,
    )
    return SuccessResponse(
        message=EcommerceMessages.PRODUCT_CREATED,
        data=ProductService(db).create(business.id, payload, images or [], actor),
    )


@router.get(
    "/businesses/{business_id}/products/{product_id}", response_model=SuccessResponse[ProductRead]
)
def get_product(
    _: ProductViewerDep, business: BusinessDep, db: DbSessionDep, product_id: UUID
) -> SuccessResponse[ProductRead]:
    return SuccessResponse(
        message=EcommerceMessages.PRODUCT_RETRIEVED,
        data=ProductService(db).get(business.id, product_id),
    )


@router.patch(
    "/businesses/{business_id}/products/{product_id}", response_model=SuccessResponse[ProductRead]
)
def update_product(
    actor: ProductManagerDep,
    business: BusinessDep,
    db: DbSessionDep,
    product_id: UUID,
    payload: ProductUpdate,
) -> SuccessResponse[ProductRead]:
    return SuccessResponse(
        message=EcommerceMessages.PRODUCT_UPDATED,
        data=ProductService(db).update(business.id, product_id, payload, actor),
    )


@router.post(
    "/businesses/{business_id}/products/{product_id}/activate",
    response_model=SuccessResponse[ProductRead],
)
def activate_product(
    actor: ProductManagerDep, business: BusinessDep, db: DbSessionDep, product_id: UUID
) -> SuccessResponse[ProductRead]:
    return SuccessResponse(
        message=EcommerceMessages.PRODUCT_ACTIVATED,
        data=ProductService(db).set_active(business.id, product_id, True, actor),
    )


@router.post(
    "/businesses/{business_id}/products/{product_id}/deactivate",
    response_model=SuccessResponse[ProductRead],
)
def deactivate_product(
    actor: ProductManagerDep, business: BusinessDep, db: DbSessionDep, product_id: UUID
) -> SuccessResponse[ProductRead]:
    return SuccessResponse(
        message=EcommerceMessages.PRODUCT_DEACTIVATED,
        data=ProductService(db).set_active(business.id, product_id, False, actor),
    )


@router.get(
    "/businesses/{business_id}/products/{product_id}/images",
    response_model=SuccessResponse[list[ProductImageRead]],
)
def list_product_images(
    _: ProductViewerDep, business: BusinessDep, db: DbSessionDep, product_id: UUID
) -> SuccessResponse[list[ProductImageRead]]:
    return SuccessResponse(
        message=EcommerceMessages.IMAGES_RETRIEVED,
        data=ProductService(db).get_image_list(business.id, product_id),
    )


@router.post(
    "/businesses/{business_id}/products/{product_id}/images",
    response_model=SuccessResponse[ProductRead],
    status_code=CREATED,
)
def upload_product_image(
    actor: ProductManagerDep,
    business: BusinessDep,
    db: DbSessionDep,
    product_id: UUID,
    file: Annotated[UploadFile, File()],
    alt_text: Annotated[str | None, Form(max_length=200)] = None,
    sort_order: Annotated[int | None, Form(ge=0), BlankAsNone] = None,
) -> SuccessResponse[ProductRead]:
    return SuccessResponse(
        message=EcommerceMessages.IMAGE_ADDED,
        data=ProductService(db).add_image(
            business.id, product_id, file, alt_text, sort_order, actor
        ),
    )


@router.delete(
    "/businesses/{business_id}/products/{product_id}/images/{image_id}",
    response_model=SuccessResponse[ProductRead],
)
def remove_product_image(
    actor: ProductManagerDep,
    business: BusinessDep,
    db: DbSessionDep,
    product_id: UUID,
    image_id: UUID,
) -> SuccessResponse[ProductRead]:
    return SuccessResponse(
        message=EcommerceMessages.IMAGE_REMOVED,
        data=ProductService(db).remove_image(business.id, product_id, image_id, actor),
    )


@router.get(
    "/businesses/{business_id}/product-categories",
    response_model=SuccessResponse[list[ProductCategoryRead]],
)
def list_product_categories(
    _: ProductViewerDep, business: BusinessDep, db: DbSessionDep
) -> SuccessResponse[list[ProductCategoryRead]]:
    return SuccessResponse(
        message=EcommerceMessages.CATEGORIES_RETRIEVED,
        data=ProductService(db).list_categories(business.id),
    )


@router.post(
    "/businesses/{business_id}/product-categories",
    response_model=SuccessResponse[ProductCategoryRead],
    status_code=CREATED,
)
def create_product_category(
    actor: ProductManagerDep,
    business: BusinessDep,
    db: DbSessionDep,
    payload: ProductCategoryCreate,
) -> SuccessResponse[ProductCategoryRead]:
    return SuccessResponse(
        message=EcommerceMessages.CATEGORY_CREATED,
        data=ProductService(db).create_category(business.id, payload, actor),
    )
