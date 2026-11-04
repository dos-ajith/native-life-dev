from uuid import UUID

from sqlalchemy.orm import Session

from app.plugins.sdk import (
    NativeBusinessScope,
    NotFoundError,
    PaginationParams,
    User,
    find_businesses_near_native_places,
)

from ..config import PLUGIN_KEY
from ..messages import EcommerceMessages
from ..models import Product
from ..repositories.product_repository import ProductRepository
from ..schemas.explore import (
    ExploreBusinessRead,
    ExploreCategoryCountRead,
    ExploreCategoryRead,
    ExploreImageRead,
    ExploreProductPage,
    ExploreProductRead,
    ExploreQuery,
)
from ..schemas.product import discount_percent
from .settings_service import SettingsService


class ExploreService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._products = ProductRepository(db)
        self._settings = SettingsService(db)

    def explore(
        self, actor: User, params: PaginationParams, query: ExploreQuery
    ) -> ExploreProductPage:
        scope = self._scope(actor, query.village_id)
        if not scope.businesses:
            return self._page([], 0, params, scope.has_native_place)
        distances = {business.id: business.distance_km for business in scope.businesses}
        products, total = self._products.explore(
            distances, query, (params.page - 1) * params.page_size, params.page_size
        )
        return self._page(self._read(products, scope), total, params, True)

    def get(
        self, actor: User, product_id: UUID, village_id: UUID | None = None
    ) -> ExploreProductRead:
        scope = self._scope(actor, village_id)
        product = self._products.get_explorable(
            [business.id for business in scope.businesses], product_id
        )
        if product is None:
            raise NotFoundError(EcommerceMessages.PRODUCT_NOT_FOUND)
        return self._read([product], scope)[0]

    def categories(
        self, actor: User, village_id: UUID | None = None
    ) -> list[ExploreCategoryCountRead]:
        scope = self._scope(actor, village_id)
        if not scope.businesses:
            return []
        return [
            ExploreCategoryCountRead(
                id=category.id, name=category.name, slug=category.slug, product_count=count
            )
            for category, count in self._products.explorable_categories(
                [business.id for business in scope.businesses]
            )
        ]

    def _scope(self, actor: User, village_id: UUID | None) -> NativeBusinessScope:
        return find_businesses_near_native_places(self._db, actor, PLUGIN_KEY, village_id)

    @staticmethod
    def _page(
        items: list[ExploreProductRead],
        total: int,
        params: PaginationParams,
        has_native_place: bool,
    ) -> ExploreProductPage:
        return ExploreProductPage(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=-(-total // params.page_size),
            has_native_place=has_native_place,
        )

    def _read(
        self, products: list[Product], scope: NativeBusinessScope
    ) -> list[ExploreProductRead]:
        businesses = {business.id: business for business in scope.businesses}
        currencies = {
            business_id: self._settings.effective(business_id)[0]
            for business_id in {product.business_id for product in products}
        }
        return [
            ExploreProductRead(
                id=product.id,
                name=product.name,
                description=product.description,
                category=(
                    ExploreCategoryRead.model_validate(product.category)
                    if product.category
                    else None
                ),
                selling_price=product.selling_price,
                original_price=product.original_price,
                discount_percent=discount_percent(product.selling_price, product.original_price),
                currency=currencies[product.business_id],
                in_stock=quantity > 0,
                available_quantity=quantity,
                images=[ExploreImageRead.model_validate(image) for image in product.images],
                business=ExploreBusinessRead(
                    id=product.business_id,
                    name=businesses[product.business_id].name,
                    distance_km=businesses[product.business_id].distance_km,
                ),
            )
            for product in products
            for quantity in [product.stock.quantity if product.stock else 0]
        ]
