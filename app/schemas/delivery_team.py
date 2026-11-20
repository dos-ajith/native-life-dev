from uuid import UUID

from pydantic import BaseModel

from app.models.user import UserStatus
from app.schemas.base import BaseReadSchema
from app.schemas.user import Email, Name, Password, Phone


class DeliveryTeamMemberCreate(BaseModel):
    first_name: Name
    last_name: Name
    email: Email
    phone: Phone | None = None
    password: Password
    promoter_id: UUID | None = None


class DeliveryTeamMemberRead(BaseReadSchema):
    id: UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    status: UserStatus
    promoter_id: UUID | None


class PromoterOptionRead(BaseReadSchema):
    id: UUID
    first_name: str
    last_name: str
    email: str | None
