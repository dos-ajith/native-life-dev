from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.plugins.sdk import CurrentActiveUserDep, DbSessionDep, PaginationDep, SuccessResponse

from ..messages import EcommerceMessages
from ..schemas.explore import (
    ExploreCategoryCountRead,
    ExploreProductPage,
    ExploreProductRead,
    ExploreQuery,
    ExploreScopeQuery,
)
from ..services.explore_service import ExploreService

router = APIRouter(prefix="/explore")


@router.get("/products", response_model=SuccessResponse[ExploreProductPage])
def explore_products(
    actor: CurrentActiveUserDep,
    db: DbSessionDep,
    params: PaginationDep,
    query: Annotated[ExploreQuery, Query()],
) -> SuccessResponse[ExploreProductPage]:
    return SuccessResponse(
        message=EcommerceMessages.EXPLORE_RETRIEVED,
        data=ExploreService(db).explore(actor, params, query),
    )


@router.get("/categories", response_model=SuccessResponse[list[ExploreCategoryCountRead]])
def explore_categories(
    actor: CurrentActiveUserDep,
    db: DbSessionDep,
    query: Annotated[ExploreScopeQuery, Query()],
) -> SuccessResponse[list[ExploreCategoryCountRead]]:
    return SuccessResponse(
        message=EcommerceMessages.EXPLORE_CATEGORIES_RETRIEVED,
        data=ExploreService(db).categories(actor, query.village_id),
    )


@router.get("/products/{product_id}", response_model=SuccessResponse[ExploreProductRead])
def get_explore_product(
    product_id: UUID,
    actor: CurrentActiveUserDep,
    db: DbSessionDep,
    query: Annotated[ExploreScopeQuery, Query()],
) -> SuccessResponse[ExploreProductRead]:
    return SuccessResponse(
        message=EcommerceMessages.EXPLORE_PRODUCT_RETRIEVED,
        data=ExploreService(db).get(actor, product_id, query.village_id),
    )
