from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.messages import BusinessMessages
from app.core.permissions import PermissionName
from app.core.storage import delete_private_document, save_business_document
from app.models.business_document import BusinessDocument
from app.models.user import User
from app.repositories.business_document_repository import BusinessDocumentRepository
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService

ENTITY_TYPE = "business_document"


class BusinessDocumentService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._settings = settings
        self._documents = BusinessDocumentRepository(db)
        self._businesses = BusinessService(db)
        self._activity_logs = ActivityLogService(db)

    def add(
        self, business_id: UUID, document_type: str, file: UploadFile, actor: User
    ) -> BusinessDocument:
        business = self._businesses.get(business_id)
        self._businesses.ensure_can_modify(business, actor, PermissionName.BUSINESS_UPDATE_ANY)
        storage_path, content_type, size_bytes = save_business_document(
            file, self._settings.private_upload_dir
        )
        try:
            document = self._documents.add(
                BusinessDocument(
                    business_id=business.id,
                    document_type=document_type,
                    file_name=file.filename or "document",
                    content_type=content_type,
                    file_size_bytes=size_bytes,
                    storage_path=storage_path,
                )
            )
        except Exception:
            delete_private_document(storage_path)
            raise
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.BUSINESS_DOCUMENT_ADDED,
            entity_type=ENTITY_TYPE,
            entity_id=document.id,
            metadata={"business_id": str(business.id), "document_type": document_type},
        )
        return document

    def list_for_business(self, business_id: UUID, actor: User) -> list[BusinessDocument]:
        business = self._businesses.get_for_actor(business_id, actor)
        return self._documents.list_by_business(business.id)

    def get_for_download(
        self, business_id: UUID, document_id: UUID, actor: User
    ) -> BusinessDocument:
        business = self._businesses.get_for_actor(business_id, actor)
        return self._get_belonging_to(business.id, document_id)

    def delete(self, business_id: UUID, document_id: UUID, actor: User) -> None:
        business = self._businesses.get(business_id)
        self._businesses.ensure_can_modify(business, actor, PermissionName.BUSINESS_UPDATE_ANY)
        document = self._get_belonging_to(business.id, document_id)
        storage_path = document.storage_path
        self._documents.delete(document)
        delete_private_document(storage_path)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.BUSINESS_DOCUMENT_REMOVED,
            entity_type=ENTITY_TYPE,
            entity_id=document_id,
            metadata={"business_id": str(business.id)},
        )

    def _get_belonging_to(self, business_id: UUID, document_id: UUID) -> BusinessDocument:
        document = self._documents.get_by_id(document_id)
        if document is None or document.business_id != business_id:
            raise NotFoundError(BusinessMessages.DOCUMENT_NOT_FOUND)
        return document
