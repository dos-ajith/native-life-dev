from uuid import UUID

from pydantic import BaseModel


class GreetingRead(BaseModel):
    plugin: str
    greeting: str


class BusinessGreetingRead(GreetingRead):
    business_id: UUID
    business_name: str
