from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.device_token import DEVICE_TOKEN_MAX_LENGTH, DevicePlatform
from app.schemas.base import BaseReadSchema

DeviceTokenValue = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=DEVICE_TOKEN_MAX_LENGTH)
]


class DeviceTokenRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: DeviceTokenValue
    platform: DevicePlatform


class DeviceTokenRemove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: DeviceTokenValue


class FirebaseWebConfigRead(BaseModel):
    apiKey: str
    authDomain: str | None
    projectId: str
    storageBucket: str | None
    messagingSenderId: str
    appId: str


class WebPushConfigRead(BaseModel):
    enabled: bool
    firebase_config: FirebaseWebConfigRead | None = None
    vapid_key: str | None = None


class DeviceTokenRead(BaseReadSchema):
    id: UUID
    platform: DevicePlatform
