from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import BaseReadSchema
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.collection import Collection

CollectionName = Annotated[NonBlankStr, Field(max_length=100)]
CollectionDescription = Annotated[NonBlankStr, Field(max_length=500)]


class CollectionCreate(BaseModel):
    name: CollectionName
    description: CollectionDescription | None = None


class CollectionUpdate(BaseModel):
    name: CollectionName | None = None
    description: CollectionDescription | None = None


class CollectionRead(BaseReadSchema):
    id: UUID
    name: str
    description: str | None
    post_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_collection(cls, collection: "Collection", post_count: int) -> "CollectionRead":
        return cls(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            post_count=post_count,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )
