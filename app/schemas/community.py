import enum
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.community import MAX_COMMUNITY_RESUBMISSIONS, Community, CommunityStatus
from app.models.community_member import CommunityMember, CommunityMemberStatus
from app.schemas.base import BaseReadSchema
from app.schemas.native_place import NativePlaceRead
from app.schemas.user import UserSummaryRead
from app.schemas.validators import NonBlankStr

CommunityName = Annotated[NonBlankStr, Field(max_length=150)]
CommunityDescription = Annotated[NonBlankStr, Field(max_length=2000)]
MaxMembers = Annotated[int, Field(ge=1)]
ReviewNote = Annotated[NonBlankStr, Field(max_length=1000)]


class CommunityCreate(BaseModel):
    name: CommunityName
    description: CommunityDescription | None = None
    auto_approve_members: bool = False
    max_members: MaxMembers | None = None


class CommunityUpdate(BaseModel):
    name: CommunityName | None = None
    description: CommunityDescription | None = None
    auto_approve_members: bool | None = None
    max_members: MaxMembers | None = None


class CommunityReject(BaseModel):
    review_note: ReviewNote


class CommunityPostRemove(BaseModel):
    reason: ReviewNote


class CommunityRead(BaseReadSchema):
    id: UUID
    owner: UserSummaryRead
    name: str
    description: str | None
    image_url: str | None
    native_place: NativePlaceRead | None
    auto_approve_members: bool
    max_members: int | None
    members_count: int
    status: CommunityStatus
    review_note: str | None
    resubmissions_left: int
    my_membership: CommunityMemberStatus | None
    is_owner: bool
    unread_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_community(
        cls,
        community: Community,
        viewer_id: UUID,
        my_membership: CommunityMemberStatus | None = None,
        unread_count: int = 0,
    ) -> "CommunityRead":
        return cls(
            id=community.id,
            owner=UserSummaryRead.model_validate(community.owner),
            name=community.name,
            description=community.description,
            image_url=community.image_url,
            native_place=(
                NativePlaceRead.from_village(community.village) if community.village else None
            ),
            auto_approve_members=community.auto_approve_members,
            max_members=community.max_members,
            members_count=community.members_count,
            status=community.status,
            review_note=community.review_note,
            resubmissions_left=max(MAX_COMMUNITY_RESUBMISSIONS - community.resubmission_count, 0),
            my_membership=my_membership,
            is_owner=community.owner_id == viewer_id,
            unread_count=unread_count,
            created_at=community.created_at,
            updated_at=community.updated_at,
        )


class NativePlaceMatch(enum.StrEnum):
    VILLAGE = "village"
    TALUK = "taluk"
    DISTRICT = "district"


class RecommendedCommunityRead(CommunityRead):
    match: NativePlaceMatch

    @classmethod
    def from_read(cls, read: CommunityRead, match: NativePlaceMatch) -> "RecommendedCommunityRead":
        values = {name: getattr(read, name) for name in CommunityRead.model_fields}
        return cls(**values, match=match)


class CommunityMemberRead(BaseReadSchema):
    user: UserSummaryRead
    status: CommunityMemberStatus
    created_at: datetime

    @classmethod
    def from_member(cls, member: CommunityMember) -> "CommunityMemberRead":
        return cls(
            user=UserSummaryRead.model_validate(member.user),
            status=member.status,
            created_at=member.created_at,
        )
