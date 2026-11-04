from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import UploadFile

from app.core.exceptions import BusinessRuleError
from app.core.messages import BusinessMessages
from app.core.storage import (
    delete_media_file,
    delete_private_document,
    save_business_document,
    save_business_image,
)
from app.models.business_document import BusinessDocument
from app.models.business_image import BusinessImage


@dataclass(frozen=True)
class BusinessUploads:
    images: list[UploadFile]
    documents: list[UploadFile]
    upload_dir: str
    private_upload_dir: str


@dataclass(frozen=True)
class StagedAttachments:
    images: list[BusinessImage]
    documents: list[BusinessDocument]


def stage_business_attachments(
    uploads: BusinessUploads, document_types: Sequence[str]
) -> StagedAttachments:
    if len(document_types) != len(uploads.documents):
        raise BusinessRuleError(BusinessMessages.DOCUMENT_TYPES_MISMATCH)
    staged = StagedAttachments(images=[], documents=[])
    try:
        for position, image_file in enumerate(uploads.images):
            image_url = save_business_image(image_file, uploads.upload_dir)
            staged.images.append(BusinessImage(image_url=image_url, sort_order=position))
        for document_file, document_type in zip(uploads.documents, document_types, strict=True):
            storage_path, content_type, size_bytes = save_business_document(
                document_file, uploads.private_upload_dir
            )
            staged.documents.append(
                BusinessDocument(
                    document_type=document_type,
                    file_name=document_file.filename or "document",
                    content_type=content_type,
                    file_size_bytes=size_bytes,
                    storage_path=storage_path,
                )
            )
    except Exception:
        discard_business_attachments(staged, uploads)
        raise
    return staged


def discard_business_attachments(staged: StagedAttachments, uploads: BusinessUploads) -> None:
    for image in staged.images:
        delete_media_file(image.image_url, uploads.upload_dir)
    for document in staged.documents:
        delete_private_document(document.storage_path)
