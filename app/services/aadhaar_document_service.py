from dataclasses import dataclass
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.messages import AadhaarDocumentMessages
from app.core.storage import delete_private_document, save_aadhaar_document
from app.models.user import User
from app.models.user_aadhaar_document import MAX_AADHAAR_FILES, UserAadhaarDocument
from app.repositories.user_aadhaar_document_repository import UserAadhaarDocumentRepository
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "user_aadhaar_document"
DEFAULT_FILE_NAME = "aadhaar"


@dataclass(frozen=True)
class StoredFile:
    file_name: str
    content_type: str
    file_size_bytes: int
    storage_path: str


class AadhaarDocumentService:
    def __init__(self, db: Session) -> None:
        self._documents = UserAadhaarDocumentRepository(db)
        self._activity_logs = ActivityLogService(db)

    def has_document(self, user: User) -> bool:
        return self._documents.exists_for_user(user.id)

    def list_files(self, user: User) -> list[UserAadhaarDocument]:
        documents = self._documents.list_by_user(user.id)
        if not documents:
            raise NotFoundError(AadhaarDocumentMessages.NOT_FOUND)
        return documents

    def get_file(self, user: User, document_id: UUID) -> UserAadhaarDocument:
        document = self._documents.get_for_user(user.id, document_id)
        if document is None:
            raise NotFoundError(AadhaarDocumentMessages.FILE_NOT_FOUND)
        return document

    def upload(
        self, user: User, files: list[UploadFile], private_upload_dir: str
    ) -> list[UserAadhaarDocument]:
        if not files:
            raise BusinessRuleError(AadhaarDocumentMessages.FILES_REQUIRED)
        if len(files) > MAX_AADHAAR_FILES:
            raise BusinessRuleError(
                AadhaarDocumentMessages.TOO_MANY_FILES.format(limit=MAX_AADHAAR_FILES)
            )
        stored = self._store_all(files, private_upload_dir)
        existing = self._documents.list_by_user(user.id)
        previous_paths = [document.storage_path for document in existing]
        try:
            documents = self._documents.replace_all(
                existing,
                [
                    UserAadhaarDocument(
                        user_id=user.id,
                        position=position,
                        file_name=file.file_name,
                        content_type=file.content_type,
                        file_size_bytes=file.file_size_bytes,
                        storage_path=file.storage_path,
                    )
                    for position, file in enumerate(stored)
                ],
            )
        except IntegrityError as exc:
            self._discard(stored)
            raise ConflictError(AadhaarDocumentMessages.UPLOAD_CONFLICT) from exc
        except Exception:
            self._discard(stored)
            raise
        for path in previous_paths:
            delete_private_document(path)
        self._log(user, documents, replaced=bool(existing))
        return documents

    def _store_all(self, files: list[UploadFile], private_upload_dir: str) -> list[StoredFile]:
        stored: list[StoredFile] = []
        try:
            for file in files:
                stored.append(self._store(file, private_upload_dir))
        except Exception:
            self._discard(stored)
            raise
        return stored

    def _store(self, file: UploadFile, private_upload_dir: str) -> StoredFile:
        storage_path, content_type, size_bytes = save_aadhaar_document(file, private_upload_dir)
        return StoredFile(
            file_name=file.filename or DEFAULT_FILE_NAME,
            content_type=content_type,
            file_size_bytes=size_bytes,
            storage_path=storage_path,
        )

    @staticmethod
    def _discard(stored: list[StoredFile]) -> None:
        for file in stored:
            delete_private_document(file.storage_path)

    def _log(self, user: User, documents: list[UserAadhaarDocument], replaced: bool) -> None:
        action = (
            ActivityAction.AADHAAR_DOCUMENT_REPLACED
            if replaced
            else ActivityAction.AADHAAR_DOCUMENT_UPLOADED
        )
        self._activity_logs.log(
            actor=user,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=documents[0].id,
            metadata={"file_count": len(documents)},
        )
