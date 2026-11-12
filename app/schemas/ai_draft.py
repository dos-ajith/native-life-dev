from uuid import UUID

from pydantic import BaseModel

from app.models.ai_draft import AIDraftKind


class AIDraftDetails(BaseModel):
    def missing_fields(self) -> list[str]:
        raise NotImplementedError


class AIDraftProgressRead[DetailsT: AIDraftDetails](BaseModel):
    details: DetailsT
    missing: list[str]


class AICreatedEntityRead(BaseModel):
    kind: AIDraftKind
    id: UUID
    title: str
    status: str
