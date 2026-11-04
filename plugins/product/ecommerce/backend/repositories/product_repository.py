from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, or_, select
from sqlalchemy.orm import Session

from ..models import Product, ProductCategory, ProductImage, StockLevel
from ..schemas.explore import ExploreQuery, ExploreSort

REFRESH = {"populate_existing": True}


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, business_id: UUID, product_id: UUID) -> Product | None:
        return self._db.scalar(
            select(Product)
            .where(Product.id == product_id, Product.business_id == business_id)
            .execution_options(**REFRESH)
        )

    def get_many(self, business_id: UUID, product_ids: list[UUID]) -> list[Product]:
        return list(
            self._db.scalars(
                select(Product)
                .where(Product.business_id == business_id, Product.id.in_(product_ids))
                .execution_options(**REFRESH)
            )
        )

    def get_by_sku(self, business_id: UUID, sku: str) -> Product | None:
        return self._db.scalar(
            select(Product).where(Product.business_id == business_id, Product.sku == sku)
        )

    def list_products(
        self,
        business_id: UUID,
        is_active: bool | None,
        category_id: UUID | None,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Product], int]:
        filters = [Product.business_id == business_id]
        if is_active is not None:
            filters.append(Product.is_active == is_active)
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if search:
            filters.append(
                or_(
                    Product.name.icontains(search, autoescape=True),
                    Product.sku.icontains(search, autoescape=True),
                )
            )
        total = self._db.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
        items = self._db.scalars(
            select(Product)
            .where(*filters)
            .order_by(Product.created_at.desc(), Product.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return list(items), total

    def search_available(
        self,
        business_distances: dict[UUID, float],
        words: list[str],
        max_price: Decimal | None,
        limit: int,
    ) -> list[Product]:
        filters = [
            Product.business_id.in_(business_distances),
            Product.is_active.is_(True),
            StockLevel.quantity > 0,
        ]
        if words:
            filters.append(
                or_(
                    *(
                        condition
                        for word in words
                        for condition in (
                            Product.name.icontains(word, autoescape=True),
                            Product.description.icontains(word, autoescape=True),
                            ProductCategory.name.icontains(word, autoescape=True),
                        )
                    )
                )
            )
        if max_price is not None:
            filters.append(Product.selling_price <= max_price)
        nearest_first = case(business_distances, value=Product.business_id, else_=None)
        return list(
            self._db.scalars(
                select(Product)
                .join(StockLevel, StockLevel.product_id == Product.id)
                .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
                .where(*filters)
                .order_by(nearest_first, Product.name, Product.id)
                .limit(limit)
            )
            .unique()
            .all()
        )

    def explore(
        self,
        business_distances: dict[UUID, float],
        query: ExploreQuery,
        offset: int,
        limit: int,
    ) -> tuple[list[Product], int]:
        filters = self._explore_filters(business_distances, query)
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(Product)
                .outerjoin(StockLevel, StockLevel.product_id == Product.id)
                .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
                .where(*filters)
            )
            or 0
        )
        nearest_first = case(business_distances, value=Product.business_id, else_=None)
        order_by = {
            ExploreSort.NEAREST: (nearest_first, Product.created_at.desc()),
            ExploreSort.NEWEST: (Product.created_at.desc(),),
            ExploreSort.PRICE_LOW: (Product.selling_price.asc(), nearest_first),
            ExploreSort.PRICE_HIGH: (Product.selling_price.desc(), nearest_first),
        }[query.sort]
        items = (
            self._db.scalars(
                select(Product)
                .outerjoin(StockLevel, StockLevel.product_id == Product.id)
                .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
                .where(*filters)
                .order_by(*order_by, Product.id)
                .offset(offset)
                .limit(limit)
            )
            .unique()
            .all()
        )
        return list(items), total

    def get_explorable(self, business_ids: list[UUID], product_id: UUID) -> Product | None:
        return self._db.scalar(
            select(Product)
            .where(
                Product.id == product_id,
                Product.business_id.in_(business_ids),
                Product.is_active.is_(True),
            )
            .execution_options(**REFRESH)
        )

    def explorable_categories(self, business_ids: list[UUID]) -> list[tuple[ProductCategory, int]]:
        rows = self._db.execute(
            select(ProductCategory, func.count(Product.id))
            .join(Product, Product.category_id == ProductCategory.id)
            .join(StockLevel, StockLevel.product_id == Product.id)
            .where(
                Product.business_id.in_(business_ids),
                Product.is_active.is_(True),
                StockLevel.quantity > 0,
                ProductCategory.is_active.is_(True),
            )
            .group_by(ProductCategory.id)
            .order_by(ProductCategory.name, ProductCategory.id)
        ).all()
        return [(category, count) for category, count in rows]

    @staticmethod
    def _explore_filters(
        business_distances: dict[UUID, float], query: ExploreQuery
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [
            Product.business_id.in_(business_distances),
            Product.is_active.is_(True),
        ]
        if query.in_stock_only:
            filters.append(StockLevel.quantity > 0)
        if query.business_id is not None:
            filters.append(Product.business_id == query.business_id)
        if query.category_id is not None:
            filters.append(Product.category_id == query.category_id)
        if query.min_price is not None:
            filters.append(Product.selling_price >= query.min_price)
        if query.max_price is not None:
            filters.append(Product.selling_price <= query.max_price)
        term = query.q.strip() if query.q else ""
        if term:
            filters.append(
                or_(
                    Product.name.icontains(term, autoescape=True),
                    Product.description.icontains(term, autoescape=True),
                    ProductCategory.name.icontains(term, autoescape=True),
                )
            )
        return filters

    def add(self, product: Product) -> Product:
        self._db.add(product)
        self._db.flush()
        return product

    def add_image(self, image: ProductImage) -> ProductImage:
        self._db.add(image)
        self._db.flush()
        return image

    def get_image(self, product_id: UUID, image_id: UUID) -> ProductImage | None:
        return self._db.scalar(
            select(ProductImage).where(
                ProductImage.id == image_id, ProductImage.product_id == product_id
            )
        )

    def delete_image(self, image: ProductImage) -> None:
        self._db.delete(image)
        self._db.flush()

    def next_image_order(self, product_id: UUID) -> int:
        highest = self._db.scalar(
            select(func.max(ProductImage.sort_order)).where(ProductImage.product_id == product_id)
        )
        return 0 if highest is None else highest + 1

    def list_categories(self, business_id: UUID) -> list[ProductCategory]:
        return list(
            self._db.scalars(
                select(ProductCategory)
                .where(
                    ProductCategory.is_active.is_(True),
                    or_(
                        ProductCategory.business_id.is_(None),
                        ProductCategory.business_id == business_id,
                    ),
                )
                .order_by(ProductCategory.name, ProductCategory.id)
            )
        )

    def get_visible_category(self, business_id: UUID, category_id: UUID) -> ProductCategory | None:
        return self._db.scalar(
            select(ProductCategory).where(
                ProductCategory.id == category_id,
                ProductCategory.is_active.is_(True),
                or_(
                    ProductCategory.business_id.is_(None),
                    ProductCategory.business_id == business_id,
                ),
            )
        )

    def get_category_by_slug(self, business_id: UUID, slug: str) -> ProductCategory | None:
        return self._db.scalar(
            select(ProductCategory).where(
                ProductCategory.slug == slug,
                or_(
                    ProductCategory.business_id.is_(None),
                    ProductCategory.business_id == business_id,
                ),
            )
        )

    def add_category(self, category: ProductCategory) -> ProductCategory:
        self._db.add(category)
        self._db.flush()
        return category
