import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.core.config import get_settings
from app.core.messages import DealMessages
from app.core.timezone import app_now, to_naive_app_time
from app.models.deal import DealStatus
from app.models.deal_invitation import DealInvitationStatus
from app.models.deal_item import PRICE_PRECISION, PRICE_SCALE
from app.models.order import DeliveryOption
from app.models.user_native_place import NativePlaceSlot
from app.schemas.base import BaseReadSchema
from app.schemas.category import CategoryRef
from app.schemas.post import PostAuthorRead
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.deal import Deal
    from app.models.deal_image import DealImage
    from app.models.deal_invitation import DealInvitation
    from app.models.deal_item import DealItem
    from app.models.user import User

MAX_DEAL_ITEMS = 50
MAX_DEAL_IMAGES = 6
DealName = Annotated[NonBlankStr, Field(max_length=255)]
DealDescription = Annotated[NonBlankStr, Field(max_length=5000)]
DealUnit = Annotated[NonBlankStr, Field(max_length=50)]
DealPickupLocation = Annotated[NonBlankStr, Field(max_length=500)]
DealDeliveryDetails = Annotated[NonBlankStr, Field(max_length=2000)]
PERCENT = Decimal(100)
DealItemName = Annotated[NonBlankStr, Field(max_length=255)]
DealItemDescription = Annotated[NonBlankStr, Field(max_length=2000)]
DealSearch = Annotated[NonBlankStr, Field(max_length=100)]
Price = Annotated[Decimal, Field(ge=0, max_digits=PRICE_PRECISION, decimal_places=PRICE_SCALE)]
Quantity = Annotated[int, Field(ge=1)]


def _ensure_in_future(value: datetime | None) -> datetime | None:
    if value is not None and to_naive_app_time(value) <= to_naive_app_time(app_now()):
        raise ValueError(DealMessages.VALID_UNTIL_IN_PAST)
    return value


def ensure_price_order(original_price: Decimal | None, deal_price: Decimal | None) -> None:
    if original_price is not None and deal_price is not None and deal_price > original_price:
        raise ValueError(DealMessages.DEAL_PRICE_ABOVE_ORIGINAL)


def ensure_end_after_start(starts_at: datetime | None, valid_until: datetime | None) -> None:
    if (
        starts_at is not None
        and valid_until is not None
        and to_naive_app_time(valid_until) <= to_naive_app_time(starts_at)
    ):
        raise ValueError(DealMessages.END_BEFORE_START)


def ensure_delivery_options_valid(
    delivery_options: list[DeliveryOption], pickup_location: str | None
) -> None:
    if len(set(delivery_options)) != len(delivery_options):
        raise ValueError(DealMessages.DELIVERY_OPTIONS_DUPLICATE)
    if DeliveryOption.SELF_PICKUP in delivery_options and pickup_location is None:
        raise ValueError(DealMessages.SELF_PICKUP_NEEDS_LOCATION)


def discount_percent(original_price: Decimal | None, deal_price: Decimal | None) -> int | None:
    if original_price is None or deal_price is None or original_price <= 0:
        return None
    return int(((original_price - deal_price) / original_price * PERCENT).to_integral_value())


def deal_image_file_url(deal_id: UUID, image_id: UUID) -> str:
    return f"{get_settings().api_v1_prefix}/deals/{deal_id}/images/{image_id}/file"


class DealItemCreate(BaseModel):
    product_id: UUID | None = None
    name: DealItemName | None = None
    description: DealItemDescription | None = None
    unit: DealUnit | None = None
    quantity: Quantity | None = None
    original_price: Price | None = None
    deal_price: Price | None = None
    image_id: UUID | None = None

    @model_validator(mode="after")
    def _validate_item(self) -> "DealItemCreate":
        ensure_price_order(self.original_price, self.deal_price)
        if self.product_id is None:
            if self.name is None:
                raise ValueError(DealMessages.ITEM_NAME_REQUIRED)
            return self
        if self.name is not None or self.unit is not None or self.original_price is not None:
            raise ValueError(DealMessages.PRODUCT_ITEM_FIELDS_LOCKED)
        if self.deal_price is None:
            raise ValueError(DealMessages.PRODUCT_DEAL_PRICE_REQUIRED)
        if self.quantity is None:
            raise ValueError(DealMessages.PRODUCT_QUANTITY_REQUIRED)
        return self


class DealItemUpdate(BaseModel):
    name: DealItemName | None = None
    description: DealItemDescription | None = None
    unit: DealUnit | None = None
    quantity: Quantity | None = None
    original_price: Price | None = None
    deal_price: Price | None = None
    image_id: UUID | None = None

    @model_validator(mode="after")
    def _validate_prices(self) -> "DealItemUpdate":
        ensure_price_order(self.original_price, self.deal_price)
        return self


class DealCreate(BaseModel):
    name: DealName
    category_id: UUID
    description: DealDescription | None = None
    business_id: UUID | None = None
    min_joiners: Quantity | None = None
    starts_at: datetime
    valid_until: datetime
    pickup_location: DealPickupLocation | None = None
    delivery_details: DealDeliveryDetails | None = None
    delivery_options: list[DeliveryOption] = Field(min_length=1)
    items: list[DealItemCreate] = Field(min_length=1, max_length=MAX_DEAL_ITEMS)

    _valid_until_in_future = field_validator("valid_until")(_ensure_in_future)

    @model_validator(mode="after")
    def _validate_form(self) -> "DealCreate":
        ensure_end_after_start(self.starts_at, self.valid_until)
        ensure_delivery_options_valid(self.delivery_options, self.pickup_location)
        if self.pickup_location is None and self.delivery_details is None:
            raise ValueError(DealMessages.PICKUP_OR_DELIVERY_REQUIRED)
        return self


class DealUpdate(BaseModel):
    name: DealName | None = None
    category_id: UUID | None = None
    description: DealDescription | None = None
    business_id: UUID | None = None
    min_joiners: Quantity | None = None
    starts_at: datetime | None = None
    valid_until: datetime | None = None
    pickup_location: DealPickupLocation | None = None
    delivery_details: DealDeliveryDetails | None = None
    delivery_options: list[DeliveryOption] | None = Field(default=None, min_length=1)

    _valid_until_in_future = field_validator("valid_until")(_ensure_in_future)


_DEAL_ITEMS_ADAPTER = TypeAdapter(list[DealItemCreate])


def parse_deal_items(raw: str) -> list[DealItemCreate]:
    return _DEAL_ITEMS_ADAPTER.validate_json(raw)


class DealListQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: DealStatus | None = None


class DealExploreQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    native: NativePlaceSlot = Field(
        default=NativePlaceSlot.PRIMARY,
        description="Which of your native places to explore: primary (default) or secondary.",
    )
    village_id: UUID | None = Field(
        default=None,
        description="Explore this village instead of one of your native places.",
    )
    category_id: UUID | None = None
    search: DealSearch | None = None


class DealImageRead(BaseModel):
    id: UUID
    file_url: str
    content_type: str
    is_thumbnail: bool
    sort_order: int

    @classmethod
    def from_image(cls, image: "DealImage") -> "DealImageRead":
        return cls(
            id=image.id,
            file_url=deal_image_file_url(image.deal_id, image.id),
            content_type=image.content_type,
            is_thumbnail=image.is_thumbnail,
            sort_order=image.sort_order,
        )


class DealItemRead(BaseModel):
    id: UUID
    product_id: UUID | None
    name: str
    description: str | None
    unit: str | None
    quantity: int | None
    remaining_quantity: int | None
    original_price: Decimal | None
    deal_price: Decimal | None
    discount_percent: int | None
    image_id: UUID | None
    image_url: str | None
    sort_order: int

    @classmethod
    def from_item(cls, item: "DealItem") -> "DealItemRead":
        return cls(
            id=item.id,
            product_id=item.product_id,
            name=item.name,
            description=item.description,
            unit=item.unit,
            quantity=item.quantity,
            remaining_quantity=(
                max(item.quantity - item.ordered_quantity, 0) if item.quantity is not None else None
            ),
            original_price=item.original_price,
            deal_price=item.deal_price,
            discount_percent=discount_percent(item.original_price, item.deal_price),
            image_id=item.image_id,
            image_url=(deal_image_file_url(item.deal_id, item.image_id) if item.image_id else None),
            sort_order=item.sort_order,
        )


class DealNativeRead(BaseModel):
    village_id: UUID
    village_name: str
    is_primary: bool


class DealBusinessRead(BaseModel):
    id: UUID
    name: str


class PromotableBusinessRead(BaseModel):
    id: UUID
    name: str
    is_mine: bool
    deals_created: int


class SellerType(enum.StrEnum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"


class DealRead(BaseReadSchema):
    id: UUID
    status: DealStatus
    name: str
    description: str | None
    category: CategoryRef
    business: DealBusinessRead | None
    creator: PostAuthorRead
    natives: list[DealNativeRead]
    items: list[DealItemRead]
    images: list[DealImageRead]
    thumbnail_url: str | None
    min_joiners: int | None
    joined_count: int
    seller_type: SellerType
    pickup_location: str | None
    delivery_details: str | None
    delivery_options: list[DeliveryOption]
    starts_at: datetime | None
    valid_until: datetime | None
    submitted_at: datetime | None
    acceptance_deadline: datetime | None
    published_at: datetime | None
    is_mine: bool
    has_joined: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_deal(cls, deal: "Deal", viewer: "User", has_joined: bool = False) -> "DealRead":
        images = [DealImageRead.from_image(image) for image in deal.images]
        thumbnail = next((image for image in images if image.is_thumbnail), None)
        business = deal.business
        return cls(
            id=deal.id,
            status=deal.status,
            name=deal.name,
            description=deal.description,
            category=CategoryRef(id=deal.category.id, name=deal.category.name),
            business=DealBusinessRead(id=business.id, name=business.name) if business else None,
            creator=PostAuthorRead.from_user(deal.creator),
            natives=[
                DealNativeRead(
                    village_id=native.village_id,
                    village_name=native.village.name,
                    is_primary=native.is_primary,
                )
                for native in deal.natives
            ],
            items=[DealItemRead.from_item(item) for item in deal.items],
            images=images,
            thumbnail_url=thumbnail.file_url if thumbnail else None,
            min_joiners=deal.min_joiners,
            joined_count=deal.joined_count,
            seller_type=SellerType.BUSINESS if deal.business_id else SellerType.INDIVIDUAL,
            pickup_location=deal.pickup_location,
            delivery_details=deal.delivery_details,
            delivery_options=[DeliveryOption(option) for option in deal.delivery_options],
            starts_at=deal.starts_at,
            valid_until=deal.valid_until,
            submitted_at=deal.submitted_at,
            acceptance_deadline=deal.acceptance_deadline,
            published_at=deal.published_at,
            is_mine=deal.created_by == viewer.id,
            has_joined=has_joined,
            created_at=deal.created_at,
            updated_at=deal.updated_at,
        )


class DealSubmissionRead(BaseModel):
    deal: DealRead
    invited_count: int


class DealInvitationRead(BaseReadSchema):
    id: UUID
    status: DealInvitationStatus
    created_at: datetime
    deal: DealRead

    @classmethod
    def from_invitation(
        cls, invitation: "DealInvitation", deal: "Deal", viewer: "User"
    ) -> "DealInvitationRead":
        return cls(
            id=invitation.id,
            status=invitation.status,
            created_at=invitation.created_at,
            deal=DealRead.from_deal(deal, viewer),
        )
