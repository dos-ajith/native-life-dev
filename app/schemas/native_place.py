from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.messages import NativePlaceMessages
from app.models.gis_village import GisVillage
from app.models.native_place_suggestion import NativePlaceSuggestion, NativePlaceSuggestionStatus
from app.models.user import User
from app.models.user_native_place import NativePlaceSlot, UserNativePlace
from app.schemas.base import BaseReadSchema
from app.schemas.geography import GisDistrictRead
from app.schemas.user import UserSummaryRead
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.services.user_native_place_service import (
        PrimaryNativePlaceResult,
        SecondaryEligibility,
    )

NativePlaceName = Annotated[NonBlankStr, Field(max_length=150)]
NativePlaceTagName = Annotated[NonBlankStr, Field(max_length=150)]
ReviewNote = Annotated[NonBlankStr, Field(max_length=1000)]


class NativePlaceSelect(BaseModel):
    village_id: UUID


class NativePlaceSuggestionCreate(BaseModel):
    name: NativePlaceName
    district_id: UUID


class NativePlaceUpdate(BaseModel):
    tag_name: NativePlaceTagName | None = None


class NativePlaceSuggestionReject(BaseModel):
    review_note: ReviewNote


class NativePlaceRead(BaseModel):
    village_id: UUID
    village_name: str
    taluk_id: UUID
    taluk_name: str
    district_id: UUID
    district_name: str
    state_id: UUID
    state_name: str
    tag_name: str | None
    image_url: str | None

    @classmethod
    def from_village(cls, village: GisVillage) -> "NativePlaceRead":
        taluk = village.taluk
        district = taluk.district
        return cls(
            village_id=village.id,
            village_name=village.name,
            taluk_id=taluk.id,
            taluk_name=taluk.name,
            district_id=district.id,
            district_name=district.name,
            state_id=district.state.id,
            state_name=district.state.name,
            tag_name=village.tag_name,
            image_url=village.image_url,
        )


class NativePlaceSearchItem(NativePlaceRead):
    is_my_native_place: bool


class NativePlaceSearchResult(BaseModel):
    places: list[NativePlaceSearchItem]
    districts: list[GisDistrictRead]


class UserNativePlaceRead(BaseModel):
    slot: NativePlaceSlot
    place: NativePlaceRead

    @classmethod
    def from_user_native_place(cls, item: UserNativePlace) -> "UserNativePlaceRead":
        return cls(slot=item.slot, place=NativePlaceRead.from_village(item.village))


class SecondaryEligibilityRead(BaseModel):
    is_eligible: bool
    note: str
    radius_km: int
    has_nearby_businesses: bool
    has_nearby_posts: bool

    @classmethod
    def from_eligibility(cls, eligibility: "SecondaryEligibility") -> "SecondaryEligibilityRead":
        note = (
            NativePlaceMessages.SECONDARY_ELIGIBLE_NOTE
            if eligibility.is_eligible
            else NativePlaceMessages.SECONDARY_INELIGIBLE_NOTE
        )
        return cls(
            is_eligible=eligibility.is_eligible,
            note=note,
            radius_km=eligibility.radius_km,
            has_nearby_businesses=eligibility.has_nearby_businesses,
            has_nearby_posts=eligibility.has_nearby_posts,
        )


class PrimaryNativePlaceRead(BaseModel):
    places: list[UserNativePlaceRead]
    secondary_eligibility: SecondaryEligibilityRead

    @classmethod
    def from_result(cls, result: "PrimaryNativePlaceResult") -> "PrimaryNativePlaceRead":
        return cls(
            places=[UserNativePlaceRead.from_user_native_place(item) for item in result.places],
            secondary_eligibility=SecondaryEligibilityRead.from_eligibility(
                result.secondary_eligibility
            ),
        )


class DistrictRef(BaseModel):
    id: UUID
    name: str


class NativePlaceSuggestionRead(BaseReadSchema):
    id: UUID
    name: str
    district: DistrictRef
    status: NativePlaceSuggestionStatus
    submitter: UserSummaryRead | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime

    @classmethod
    def from_suggestion(cls, suggestion: NativePlaceSuggestion) -> "NativePlaceSuggestionRead":
        submitter = suggestion.submitter
        return cls(
            id=suggestion.id,
            name=suggestion.name,
            district=DistrictRef(id=suggestion.district.id, name=suggestion.district.name),
            status=suggestion.status,
            submitter=UserSummaryRead.model_validate(submitter) if submitter else None,
            reviewed_at=suggestion.reviewed_at,
            review_note=suggestion.review_note,
            created_at=suggestion.created_at,
        )


class NativeAdminRead(BaseModel):
    village_id: UUID
    village_name: str
    user_id: UUID
    first_name: str
    last_name: str
    email: str | None

    @classmethod
    def from_models(cls, village: GisVillage, admin: User) -> "NativeAdminRead":
        return cls(
            village_id=village.id,
            village_name=village.name,
            user_id=admin.id,
            first_name=admin.first_name,
            last_name=admin.last_name,
            email=admin.email,
        )
