from dataclasses import dataclass
from datetime import date

from app.models.user import UserGender


@dataclass(frozen=True)
class RegistrationDetails:
    registration_token: str
    first_name: str
    last_name: str
    ip_address: str | None = None
    user_agent: str | None = None
    gender: UserGender | None = None
    date_of_birth: date | None = None
