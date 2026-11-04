from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.plugins.sdk import (
    AITool,
    AIToolContext,
    NativeBusinessScope,
    find_businesses_near_native_places,
)

from .config import (
    AI_DESCRIPTION_MAX_LENGTH,
    AI_MAX_RESULTS,
    AI_QUERY_MAX_LENGTH,
    AI_QUERY_MIN_WORD_LENGTH,
    PLUGIN_KEY,
)
from .models import Product
from .repositories.product_repository import ProductRepository
from .services.settings_service import SettingsService


class SearchProductsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(
        default=None,
        max_length=AI_QUERY_MAX_LENGTH,
        description="Product keywords such as 'saree', 'honey' or 'phone'.",
    )
    max_price: Decimal | None = Field(
        default=None, ge=0, description="Highest price the user is willing to pay."
    )
    limit: int = Field(default=AI_MAX_RESULTS, ge=1, le=AI_MAX_RESULTS)


class ProductReferenceRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    category: str | None
    selling_price: Decimal
    currency: str
    business_id: UUID
    business_name: str
    distance_km: float
    image_url: str | None


class SearchProductsResult(BaseModel):
    has_native_place: bool
    products: list[ProductReferenceRead]


def _words(query: str | None) -> list[str]:
    if query is None:
        return []
    return [word for word in query.split() if len(word) >= AI_QUERY_MIN_WORD_LENGTH]


class EcommerceSearchProductsTool(AITool[SearchProductsArgs]):
    name = f"{PLUGIN_KEY}_search_products"
    description = (
        "Search real products on sale from Native Life businesses near the user's native "
        "places, nearest business first. Only active products that are in stock are "
        "returned. Returns up to 5 products with id, name, description, category, selling_price, "
        "currency, business name, distance in km and an image. Use it when the user wants "
        "to buy or find something from their native place. Recommend only returned "
        "products and state only the returned fields; never claim ratings, delivery, "
        "discounts or exact stock. If has_native_place is false, tell the user to set "
        "their native place in their profile. If the list is empty, say no matching "
        "products were found near their native places."
    )
    args_model = SearchProductsArgs

    def execute(
        self, context: AIToolContext, arguments: SearchProductsArgs
    ) -> SearchProductsResult:
        scope = find_businesses_near_native_places(context.db, context.actor, PLUGIN_KEY)
        if not scope.businesses:
            return SearchProductsResult(has_native_place=scope.has_native_place, products=[])
        products = ProductRepository(context.db).search_available(
            {business.id: business.distance_km for business in scope.businesses},
            _words(arguments.query),
            arguments.max_price,
            arguments.limit,
        )
        return SearchProductsResult(
            has_native_place=True, products=self._references(context, scope, products)
        )

    @staticmethod
    def _references(
        context: AIToolContext, scope: NativeBusinessScope, products: list[Product]
    ) -> list[ProductReferenceRead]:
        businesses = {business.id: business for business in scope.businesses}
        settings = SettingsService(context.db)
        currencies = {
            business_id: settings.effective(business_id)[0]
            for business_id in {product.business_id for product in products}
        }
        return [
            ProductReferenceRead(
                id=product.id,
                name=product.name,
                description=(
                    product.description[:AI_DESCRIPTION_MAX_LENGTH] if product.description else None
                ),
                category=product.category.name if product.category else None,
                selling_price=product.selling_price,
                currency=currencies[product.business_id],
                business_id=product.business_id,
                business_name=businesses[product.business_id].name,
                distance_km=businesses[product.business_id].distance_km,
                image_url=product.images[0].url if product.images else None,
            )
            for product in products
        ]
