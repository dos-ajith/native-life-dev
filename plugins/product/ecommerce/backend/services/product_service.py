import re
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.plugins.sdk import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    Page,
    PaginationParams,
    StoredImage,
    User,
    delete_plugin_image,
    record_activity,
    save_plugin_image,
)

from ..activity_actions import EcommerceAction, EcommerceEntity
from ..config import MAX_IMAGE_BYTES, MAX_PRODUCT_IMAGES, PLUGIN_KEY
from ..database_errors import is_unique_violation
from ..messages import EcommerceMessages
from ..models import Product, ProductCategory, ProductImage, StockLevel
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.product_repository import ProductRepository
from ..schemas.product import (
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCreate,
    ProductImageRead,
    ProductRead,
    ProductUpdate,
)
from ..stock_rules import StockReason
from .stock_ledger import StockLedger

SLUG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")
CATEGORY_SLUG_MAX_LENGTH = 120


def _slugify(name: str) -> str:
    return SLUG_SEPARATOR_PATTERN.sub("-", name.lower()).strip("-")


class ProductService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._products = ProductRepository(db)
        self._inventory = InventoryRepository(db)
        self._ledger = StockLedger(self._inventory)

    def list_products(
        self,
        business_id: UUID,
        params: PaginationParams,
        is_active: bool | None,
        category_id: UUID | None,
        search: str | None,
    ) -> Page[ProductRead]:
        items, total = self._products.list_products(
            business_id,
            is_active,
            category_id,
            search,
            (params.page - 1) * params.page_size,
            params.page_size,
        )
        return Page[ProductRead].create(
            [ProductRead.model_validate(item) for item in items], total, params
        )

    def get(self, business_id: UUID, product_id: UUID) -> ProductRead:
        return ProductRead.model_validate(self._require(business_id, product_id))

    def create(
        self,
        business_id: UUID,
        payload: ProductCreate,
        images: list[UploadFile],
        actor: User,
    ) -> ProductRead:
        self._ensure_sku_free(business_id, payload.sku)
        self._ensure_category(business_id, payload.category_id)
        self._ensure_image_count(len(images))
        stored_images: list[StoredImage] = []
        try:
            stored_images = [
                save_plugin_image(image, PLUGIN_KEY, str(business_id), MAX_IMAGE_BYTES)
                for image in images
            ]
            product = self._stage_product(business_id, payload, actor)
            for order, stored in enumerate(stored_images):
                self._products.add_image(
                    ProductImage(
                        product_id=product.id,
                        url=stored.url,
                        sort_order=order,
                        content_type=stored.content_type,
                        size_bytes=stored.size_bytes,
                    )
                )
            self._commit_unique()
        except Exception:
            self._db.rollback()
            for stored in stored_images:
                delete_plugin_image(stored.url)
            raise
        self._log(
            actor,
            EcommerceAction.PRODUCT_CREATED,
            product.id,
            business_id,
            {"image_count": len(stored_images)},
        )
        return self.get(business_id, product.id)

    def _stage_product(self, business_id: UUID, payload: ProductCreate, actor: User) -> Product:
        product = self._products.add(
            Product(
                business_id=business_id,
                category_id=payload.category_id,
                name=payload.name,
                description=payload.description,
                sku=payload.sku,
                selling_price=payload.selling_price,
                original_price=payload.original_price or payload.selling_price,
                is_active=payload.is_active,
                is_bulk_promotable=payload.is_bulk_promotable,
                is_individually_promotable=payload.is_individually_promotable,
                created_by=actor.id,
            )
        )
        stock = self._inventory.add_stock(
            StockLevel(
                product_id=product.id,
                business_id=business_id,
                quantity=0,
                low_stock_threshold=payload.low_stock_threshold,
            )
        )
        if payload.quantity > 0:
            self._ledger.apply(stock, product.name, payload.quantity, StockReason.INITIAL, actor.id)
        return product

    def _apply_prices(self, product: Product, payload: ProductUpdate, changed: list[str]) -> None:
        selling_price = (
            payload.selling_price if payload.selling_price is not None else product.selling_price
        )
        original_price = (
            payload.original_price if payload.original_price is not None else product.original_price
        )
        if selling_price > original_price:
            raise BusinessRuleError(EcommerceMessages.PRICE_ABOVE_ORIGINAL)
        if selling_price != product.selling_price:
            product.selling_price = selling_price
            changed.append("selling_price")
        if original_price != product.original_price:
            product.original_price = original_price
            changed.append("original_price")

    def _ensure_image_count(self, count: int) -> None:
        if count > MAX_PRODUCT_IMAGES:
            raise BusinessRuleError(
                EcommerceMessages.TOO_MANY_IMAGES.format(limit=MAX_PRODUCT_IMAGES)
            )

    def update(
        self, business_id: UUID, product_id: UUID, payload: ProductUpdate, actor: User
    ) -> ProductRead:
        product = self._require(business_id, product_id)
        provided = payload.model_fields_set
        changed: list[str] = []
        if payload.sku is not None and payload.sku != product.sku:
            self._ensure_sku_free(business_id, payload.sku)
            product.sku = payload.sku
            changed.append("sku")
        if payload.category_id is not None and payload.category_id != product.category_id:
            self._ensure_category(business_id, payload.category_id)
            product.category_id = payload.category_id
            changed.append("category_id")
        if payload.selling_price is not None or payload.original_price is not None:
            self._apply_prices(product, payload, changed)
        for flag in ("is_bulk_promotable", "is_individually_promotable"):
            value = getattr(payload, flag)
            if value is not None and value != getattr(product, flag):
                setattr(product, flag, value)
                changed.append(flag)
        if payload.name is not None and payload.name != product.name:
            product.name = payload.name
            changed.append("name")
        if "description" in provided and payload.description != product.description:
            product.description = payload.description
            changed.append("description")
        if changed:
            self._commit_unique()
            self._log(
                actor, EcommerceAction.PRODUCT_UPDATED, product_id, business_id, {"fields": changed}
            )
        return self.get(business_id, product_id)

    def set_active(
        self, business_id: UUID, product_id: UUID, active: bool, actor: User
    ) -> ProductRead:
        product = self._require(business_id, product_id)
        if product.is_active != active:
            product.is_active = active
            self._db.commit()
            action = (
                EcommerceAction.PRODUCT_ACTIVATED if active else EcommerceAction.PRODUCT_DEACTIVATED
            )
            self._log(actor, action, product_id, business_id)
        return self.get(business_id, product_id)

    def add_image(
        self,
        business_id: UUID,
        product_id: UUID,
        file: UploadFile,
        alt_text: str | None,
        sort_order: int | None,
        actor: User,
    ) -> ProductRead:
        product = self._require(business_id, product_id)
        self._ensure_image_count(len(product.images) + 1)
        stored = save_plugin_image(file, PLUGIN_KEY, str(business_id), MAX_IMAGE_BYTES)
        try:
            image = self._products.add_image(
                ProductImage(
                    product_id=product_id,
                    url=stored.url,
                    alt_text=alt_text,
                    sort_order=(
                        sort_order
                        if sort_order is not None
                        else self._products.next_image_order(product_id)
                    ),
                    content_type=stored.content_type,
                    size_bytes=stored.size_bytes,
                )
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            delete_plugin_image(stored.url)
            raise
        self._log(
            actor,
            EcommerceAction.PRODUCT_IMAGE_ADDED,
            product_id,
            business_id,
            {"image_id": str(image.id)},
        )
        return self.get(business_id, product_id)

    def remove_image(
        self, business_id: UUID, product_id: UUID, image_id: UUID, actor: User
    ) -> ProductRead:
        self._require(business_id, product_id)
        image = self._products.get_image(product_id, image_id)
        if image is None:
            raise NotFoundError(EcommerceMessages.IMAGE_NOT_FOUND)
        url = image.url
        self._products.delete_image(image)
        self._db.commit()
        delete_plugin_image(url)
        self._log(
            actor,
            EcommerceAction.PRODUCT_IMAGE_REMOVED,
            product_id,
            business_id,
            {"image_id": str(image_id)},
        )
        return self.get(business_id, product_id)

    def get_image_list(self, business_id: UUID, product_id: UUID) -> list[ProductImageRead]:
        product = self._require(business_id, product_id)
        return [ProductImageRead.model_validate(image) for image in product.images]

    def list_categories(self, business_id: UUID) -> list[ProductCategoryRead]:
        return [
            ProductCategoryRead.model_validate(category)
            for category in self._products.list_categories(business_id)
        ]

    def create_category(
        self, business_id: UUID, payload: ProductCategoryCreate, actor: User
    ) -> ProductCategoryRead:
        slug = _slugify(payload.name)
        if not slug:
            raise BusinessRuleError(EcommerceMessages.CATEGORY_NAME_INVALID)
        if self._products.get_category_by_slug(business_id, slug) is not None:
            raise ConflictError(EcommerceMessages.CATEGORY_EXISTS)
        category = self._products.add_category(
            ProductCategory(
                business_id=business_id,
                name=payload.name.strip(),
                slug=slug[:CATEGORY_SLUG_MAX_LENGTH],
            )
        )
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            if not is_unique_violation(exc):
                raise
            raise ConflictError(EcommerceMessages.CATEGORY_EXISTS) from exc
        record_activity(
            self._db,
            actor,
            EcommerceAction.CATEGORY_CREATED,
            EcommerceEntity.PRODUCT_CATEGORY,
            category.id,
            {"business_id": str(business_id)},
        )
        return ProductCategoryRead.model_validate(category)

    def _require(self, business_id: UUID, product_id: UUID) -> Product:
        product = self._products.get(business_id, product_id)
        if product is None:
            raise NotFoundError(EcommerceMessages.PRODUCT_NOT_FOUND)
        return product

    def _ensure_sku_free(self, business_id: UUID, sku: str) -> None:
        if self._products.get_by_sku(business_id, sku) is not None:
            raise ConflictError(EcommerceMessages.SKU_EXISTS)

    def _ensure_category(self, business_id: UUID, category_id: UUID) -> None:
        if self._products.get_visible_category(business_id, category_id) is None:
            raise NotFoundError(EcommerceMessages.CATEGORY_NOT_FOUND)

    def _commit_unique(self) -> None:
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            if not is_unique_violation(exc):
                raise
            raise ConflictError(EcommerceMessages.SKU_EXISTS) from exc

    def _log(
        self,
        actor: User,
        action: str,
        product_id: UUID,
        business_id: UUID,
        extra: dict[str, object] | None = None,
    ) -> None:
        record_activity(
            self._db,
            actor,
            action,
            EcommerceEntity.PRODUCT,
            product_id,
            {"business_id": str(business_id), **(extra or {})},
        )
