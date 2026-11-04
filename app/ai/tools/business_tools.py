from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.base import AITool, SearchQuery, ToolContext
from app.schemas.business import BusinessDiscoveryQuery, BusinessSummaryRead
from app.schemas.category import CategoryRef
from app.services.business_service import AI_DISCOVERY_MAX_RESULTS, BusinessService
from app.services.category_service import CategoryService

_MAX_CATEGORY_RESULTS = 10


class SearchBusinessCategoriesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: SearchQuery


class BusinessCategoryReferenceRead(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None


class SearchBusinessCategoriesResult(BaseModel):
    categories: list[BusinessCategoryReferenceRead]


class SearchBusinessCategoriesTool(AITool[SearchBusinessCategoriesArgs]):
    name = "search_business_categories"
    description = (
        "Search real Native Life business categories by name (e.g. 'restaurant', 'food'). "
        "Returns up to 10 active categories with their id and parent_id. Use an id from "
        "the result as category_id in search_businesses; never guess a category id."
    )
    args_model = SearchBusinessCategoriesArgs

    def execute(
        self, context: ToolContext, arguments: SearchBusinessCategoriesArgs
    ) -> SearchBusinessCategoriesResult:
        categories = CategoryService(context.db).search_active(
            arguments.query, _MAX_CATEGORY_RESULTS
        )
        return SearchBusinessCategoriesResult(
            categories=[
                BusinessCategoryReferenceRead(
                    id=category.id, name=category.name, parent_id=category.parent_id
                )
                for category in categories
            ]
        )


class SearchBusinessesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: SearchQuery | None = Field(
        default=None, description="Free-text words to match against the business name."
    )
    category_id: UUID | None = Field(
        default=None,
        description=(
            "Category id from search_business_categories. Includes businesses in that "
            "category's sub-categories."
        ),
    )
    limit: int = Field(default=AI_DISCOVERY_MAX_RESULTS, ge=1, le=AI_DISCOVERY_MAX_RESULTS)


class BusinessReferenceRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    category: CategoryRef
    parent_category: CategoryRef | None


def to_business_reference(item: BusinessSummaryRead) -> BusinessReferenceRead:
    return BusinessReferenceRead(
        id=item.id,
        name=item.name,
        description=item.description,
        category=CategoryRef(id=item.category.id, name=item.category.name),
        parent_category=item.category.parent,
    )


class SearchBusinessesResult(BaseModel):
    businesses: list[BusinessReferenceRead]
    total: int


class SearchBusinessesTool(AITool[SearchBusinessesArgs]):
    name = "search_businesses"
    description = (
        "Search real, active Native Life businesses by name and/or category. Returns up to "
        "10 businesses with only id, name, description, category and parent category, plus "
        "the total match count. Businesses currently have no location, rating, price, "
        "hours or services data, so never state any. Recommend only returned businesses; "
        "if the list is empty, say no matching Native Life businesses were found."
    )
    args_model = SearchBusinessesArgs

    def execute(
        self, context: ToolContext, arguments: SearchBusinessesArgs
    ) -> SearchBusinessesResult:
        query = BusinessDiscoveryQuery(search=arguments.query, category_id=arguments.category_id)
        items, total = BusinessService(context.db).search_for_ai(query, arguments.limit)
        return SearchBusinessesResult(
            businesses=[to_business_reference(item) for item in items],
            total=total,
        )
