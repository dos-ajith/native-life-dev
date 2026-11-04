from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.messages import BusinessMessages
from app.models.business import Business, BusinessStatus, BusinessVerificationStatus
from app.models.business_document import BusinessDocument, BusinessDocumentStatus
from app.models.business_image import BusinessImage
from app.schemas.base import BaseReadSchema
from app.schemas.category import CategoryRef, CategoryWithParentRead
from app.schemas.post import Latitude, Longitude
from app.schemas.validators import AlphanumericStr, NonBlankStr

BusinessName = Annotated[AlphanumericStr, Field(max_length=255)]
BusinessDescription = NonBlankStr
DocumentType = Annotated[NonBlankStr, Field(max_length=100)]
DEFAULT_DISCOVERY_RADIUS_METERS = 2000
MIN_DISCOVERY_RADIUS_METERS = 100
MAX_DISCOVERY_RADIUS_METERS = 50000
DiscoveryRadius = Annotated[
    int, Field(ge=MIN_DISCOVERY_RADIUS_METERS, le=MAX_DISCOVERY_RADIUS_METERS)
]


class BusinessLocationInput(BaseModel):
    latitude: Latitude | None = None
    longitude: Longitude | None = None

    @model_validator(mode="after")
    def _require_both_coordinates(self) -> "BusinessLocationInput":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(BusinessMessages.LOCATION_INCOMPLETE)
        return self


class BusinessCreate(BusinessLocationInput):
    name: BusinessName
    category_id: UUID
    description: BusinessDescription | None = None
    document_types: list[DocumentType] = Field(default_factory=list)


class BusinessUpdate(BusinessLocationInput):
    name: BusinessName | None = None
    category_id: UUID | None = None
    description: BusinessDescription | None = None
    status: BusinessStatus | None = None


class BusinessRead(BaseReadSchema):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    category: CategoryWithParentRead | None
    latitude: float | None
    longitude: float | None
    status: BusinessStatus
    verification_status: BusinessVerificationStatus
    review_note: str | None
    reviewed_at: datetime | None
    resubmission_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_business(cls, business: Business) -> "BusinessRead":
        category = business.category
        category_read = None
        if category is not None:
            parent = category.parent
            category_read = CategoryWithParentRead(
                id=category.id,
                name=category.name,
                parent=CategoryRef(id=parent.id, name=parent.name) if parent else None,
            )
        return cls(
            id=business.id,
            owner_id=business.owner_id,
            name=business.name,
            description=business.description,
            category=category_read,
            latitude=business.latitude,
            longitude=business.longitude,
            status=business.status,
            verification_status=business.verification_status,
            review_note=business.review_note,
            reviewed_at=business.reviewed_at,
            resubmission_count=business.resubmission_count,
            created_at=business.created_at,
            updated_at=business.updated_at,
        )


class BusinessImageRead(BaseReadSchema):
    id: UUID
    business_id: UUID
    image_url: str
    sort_order: int
    created_at: datetime


class BusinessDetailRead(BusinessRead):
    images: list[BusinessImageRead]

    @classmethod
    def from_business_with_images(
        cls, business: Business, images: list[BusinessImage]
    ) -> "BusinessDetailRead":
        base = BusinessRead.from_business(business)
        return cls(
            **{name: getattr(base, name) for name in BusinessRead.model_fields},
            images=[BusinessImageRead.model_validate(image) for image in images],
        )


class BusinessSummaryRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    category: CategoryWithParentRead
    distance_meters: int | None = None
    image_url: str | None = None


class BusinessDiscoveryQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    search: Annotated[str, Field(max_length=255)] | None = None
    category_id: UUID | None = None
    village_id: UUID | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    radius_meters: DiscoveryRadius | None = None

    @model_validator(mode="after")
    def _validate_location_filter(self) -> "BusinessDiscoveryQuery":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(BusinessMessages.LOCATION_INCOMPLETE)
        if self.radius_meters is not None and self.latitude is None:
            raise ValueError(BusinessMessages.RADIUS_REQUIRES_LOCATION)
        return self

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def effective_radius_meters(self) -> int:
        return self.radius_meters or DEFAULT_DISCOVERY_RADIUS_METERS


class BusinessDocumentRead(BaseReadSchema):
    id: UUID
    business_id: UUID
    document_type: str
    file_name: str
    content_type: str
    file_size_bytes: int
    status: BusinessDocumentStatus
    verified_at: datetime | None
    created_at: datetime


class BusinessCreatedRead(BusinessDetailRead):
    documents: list[BusinessDocumentRead]

    @classmethod
    def from_created(
        cls,
        business: Business,
        images: list[BusinessImage],
        documents: list[BusinessDocument],
    ) -> "BusinessCreatedRead":
        base = BusinessDetailRead.from_business_with_images(business, images)
        return cls(
            **{name: getattr(base, name) for name in BusinessDetailRead.model_fields},
            documents=[BusinessDocumentRead.model_validate(document) for document in documents],
        )
