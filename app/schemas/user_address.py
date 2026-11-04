from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.messages import UserAddressMessages
from app.schemas.base import BaseReadSchema
from app.schemas.native_place import NativePlaceRead
from app.schemas.post import Latitude, Longitude
from app.schemas.validators import MobileNumberStr, NameStr, NonBlankStr

if TYPE_CHECKING:
    from app.models.user_address import UserAddress
    from app.services.user_address_service import AddressMapCenter

PINCODE_PATTERN = r"^[1-9][0-9]{5}$"

AddressLabel = Annotated[NonBlankStr, Field(max_length=50)]
AddressFullName = Annotated[NameStr, Field(max_length=150)]
AddressLine = Annotated[NonBlankStr, Field(max_length=255)]
AddressLandmark = Annotated[NonBlankStr, Field(max_length=150)]
AddressPincode = Annotated[str, Field(pattern=PINCODE_PATTERN)]


class UserAddressCreate(BaseModel):
    label: AddressLabel
    full_name: AddressFullName
    phone: MobileNumberStr
    address_line: AddressLine
    landmark: AddressLandmark | None = None
    pincode: AddressPincode
    latitude: Latitude
    longitude: Longitude
    is_default: bool = False


class UserAddressUpdate(BaseModel):
    label: AddressLabel | None = Field(default=None)
    full_name: AddressFullName | None = Field(default=None)
    phone: MobileNumberStr | None = Field(default=None)
    address_line: AddressLine | None = Field(default=None)
    landmark: AddressLandmark | None = None
    pincode: AddressPincode | None = Field(default=None)
    latitude: Latitude | None = Field(default=None)
    longitude: Longitude | None = Field(default=None)

    @model_validator(mode="after")
    def _require_both_coordinates(self) -> "UserAddressUpdate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(UserAddressMessages.LOCATION_INCOMPLETE)
        return self


class UserAddressRead(BaseReadSchema):
    id: UUID
    label: str
    full_name: str
    phone: str
    address_line: str
    landmark: str | None
    pincode: str
    latitude: float
    longitude: float
    place: NativePlaceRead
    is_default: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_address(cls, address: "UserAddress") -> "UserAddressRead":
        return cls(
            id=address.id,
            label=address.label,
            full_name=address.full_name,
            phone=address.phone,
            address_line=address.address_line,
            landmark=address.landmark,
            pincode=address.pincode,
            latitude=address.latitude,
            longitude=address.longitude,
            place=NativePlaceRead.from_village(address.village),
            is_default=address.is_default,
            created_at=address.created_at,
            updated_at=address.updated_at,
        )


class AddressMapCenterRead(BaseModel):
    latitude: float
    longitude: float
    place: NativePlaceRead

    @classmethod
    def from_center(cls, center: "AddressMapCenter") -> "AddressMapCenterRead":
        return cls(
            latitude=center.latitude,
            longitude=center.longitude,
            place=NativePlaceRead.from_village(center.village),
        )
