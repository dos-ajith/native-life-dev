from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.auth import AuthenticatedResult, RegistrationRequiredResult
from app.schemas.validators import MobileNumberStr

OTP_PATTERN = r"^\d{4,8}$"


class PhoneOtpRequest(BaseModel):
    phone: MobileNumberStr


class PhoneOtpSent(BaseModel):
    phone: str
    expires_in_seconds: int
    resend_available_in_seconds: int
    dev_otp: str | None = None


class PhoneOtpVerifyRequest(BaseModel):
    phone: MobileNumberStr
    otp: str = Field(pattern=OTP_PATTERN)


class PhoneRegistrationRequiredResult(RegistrationRequiredResult):
    phone: str


PhoneVerifyResult = Annotated[
    AuthenticatedResult | PhoneRegistrationRequiredResult, Field(discriminator="status")
]
