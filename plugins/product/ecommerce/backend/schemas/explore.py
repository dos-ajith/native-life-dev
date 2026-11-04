import enum
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.plugins.sdk import BaseReadSchema, Page

from ..config import MAX_PRICE
from ..messages import EcommerceMessages

SEARCH_MAX_LENGTH = 100


class ExploreSort(enum.StrEnum):
    NEAREST = "nearest"
    NEWEST = "newest"
    PRICE_LOW = "price_low"
    PRICE_HIGH = "price_high"


class ExploreScopeQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    village_id: UUID | None = None


class ExploreQuery(ExploreScopeQuery):
    q: Annotated[str, Field(max_length=SEARCH_MAX_LENGTH)] | None = None
    category_id: UUID | None = None
    business_id: UUID | None = None
    min_price: Annotated[Decimal, Field(ge=0, le=MAX_PRICE)] | None = None
    max_price: Annotated[Decimal, Field(ge=0, le=MAX_PRICE)] | None = None
    sort: ExploreSort = ExploreSort.NEAREST
    in_stock_only: bool = True

    @model_validator(mode="after")
    def _price_range(self) -> "ExploreQuery":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError(EcommerceMessages.PRICE_RANGE_INVALID)
        return self


class ExploreBusinessRead(BaseModel):
    id: UUID
    name: str
    distance_km: float


class ExploreImageRead(BaseReadSchema):
    url: str
    alt_text: str | None
    sort_order: int


class ExploreCategoryRead(BaseReadSchema):
    id: UUID
    name: str
    slug: str


class ExploreProductRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    category: ExploreCategoryRead | None
    selling_price: Decimal
    original_price: Decimal
    discount_percent: Decimal
    currency: str
    in_stock: bool
    available_quantity: int
    images: list[ExploreImageRead]
    business: ExploreBusinessRead


class ExploreProductPage(Page[ExploreProductRead]):
    has_native_place: bool = True


class ExploreCategoryCountRead(ExploreCategoryRead):
    product_count: int
