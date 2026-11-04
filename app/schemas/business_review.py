import enum
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.business import BusinessStatus, BusinessVerificationStatus
from app.models.business_document import BusinessDocumentStatus
from app.schemas.base import BaseReadSchema
from app.schemas.business import BusinessDocumentRead, BusinessImageRead, BusinessRead
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.business_document import BusinessDocument
    from app.models.business_image import BusinessImage
    from app.models.user import User
    from app.repositories.business_repository import BusinessCounts

ReviewNote = Annotated[NonBlankStr, Field(max_length=1000)]
ReviewableDocumentStatus = Literal[
    BusinessDocumentStatus.UNDER_REVIEW,
    BusinessDocumentStatus.VERIFIED,
    BusinessDocumentStatus.REJECTED,
]


class BusinessReviewScope(enum.StrEnum):
    ROUTINE_LOCAL = "routine_local"
    PLATFORM_ESCALATION = "platform_escalation"


class BusinessReviewQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    scope: BusinessReviewScope | None = None
    owner_id: UUID | None = None
    village_id: UUID | None = None
    verification_status: BusinessVerificationStatus | None = None
    status: BusinessStatus | None = None
    category_id: UUID | None = None
    search: Annotated[str, Field(max_length=255)] | None = None


class BusinessReject(BaseModel):
    review_note: ReviewNote


class BusinessEscalate(BaseModel):
    escalation_note: ReviewNote


class BusinessDocumentReview(BaseModel):
    status: ReviewableDocumentStatus


class BusinessOwnerRead(BaseModel):
    id: UUID
    name: str
    email: str | None
    phone: str | None

    @classmethod
    def from_user(cls, user: "User") -> "BusinessOwnerRead":
        return cls(
            id=user.id,
            name=f"{user.first_name} {user.last_name}".strip(),
            email=user.email,
            phone=user.phone,
        )


class BusinessReviewRead(BusinessRead):
    owner: BusinessOwnerRead
    escalated_at: datetime | None
    escalated_by: UUID | None
    escalation_note: str | None

    @classmethod
    def from_business_for_review(cls, business: "Business") -> "BusinessReviewRead":
        base = BusinessRead.from_business(business)
        return cls(
            **{name: getattr(base, name) for name in BusinessRead.model_fields},
            owner=BusinessOwnerRead.from_user(business.owner),
            escalated_at=business.escalated_at,
            escalated_by=business.escalated_by,
            escalation_note=business.escalation_note,
        )


class BusinessReviewDetailRead(BusinessReviewRead):
    images: list[BusinessImageRead]
    documents: list[BusinessDocumentRead]

    @classmethod
    def from_parts(
        cls,
        business: "Business",
        images: list["BusinessImage"],
        documents: list["BusinessDocument"],
    ) -> "BusinessReviewDetailRead":
        base = BusinessReviewRead.from_business_for_review(business)
        return cls(
            **{name: getattr(base, name) for name in BusinessReviewRead.model_fields},
            images=[BusinessImageRead.model_validate(image) for image in images],
            documents=[BusinessDocumentRead.model_validate(document) for document in documents],
        )


class BusinessCountsRead(BaseReadSchema):
    registered: int
    active: int
    pending_verification: int
    routine_local: int
    platform_escalation: int

    @classmethod
    def from_counts(cls, counts: "BusinessCounts") -> "BusinessCountsRead":
        return cls(
            registered=counts.registered,
            active=counts.active,
            pending_verification=counts.pending_verification,
            routine_local=counts.routine_local,
            platform_escalation=counts.platform_escalation,
        )
