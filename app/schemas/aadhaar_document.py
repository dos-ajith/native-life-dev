from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas.base import BaseReadSchema

if TYPE_CHECKING:
    from app.models.user_aadhaar_document import UserAadhaarDocument


def aadhaar_file_url(document_id: UUID) -> str:
    return f"{get_settings().api_v1_prefix}/users/me/aadhaar-document/files/{document_id}"


class AadhaarDocumentFileRead(BaseReadSchema):
    id: UUID
    position: int
    file_name: str
    content_type: str
    file_size_bytes: int
    file_url: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: "UserAadhaarDocument") -> "AadhaarDocumentFileRead":
        return cls(
            id=document.id,
            position=document.position,
            file_name=document.file_name,
            content_type=document.content_type,
            file_size_bytes=document.file_size_bytes,
            file_url=aadhaar_file_url(document.id),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


class AadhaarDocumentRead(BaseModel):
    files: list[AadhaarDocumentFileRead]

    @classmethod
    def from_documents(cls, documents: list["UserAadhaarDocument"]) -> "AadhaarDocumentRead":
        return cls(
            files=[AadhaarDocumentFileRead.from_document(document) for document in documents]
        )
