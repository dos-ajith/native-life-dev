from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.user_aadhaar_document import UserAadhaarDocument


class UserAadhaarDocumentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(self, user_id: UUID) -> list[UserAadhaarDocument]:
        return list(
            self._db.scalars(
                select(UserAadhaarDocument)
                .where(UserAadhaarDocument.user_id == user_id)
                .order_by(UserAadhaarDocument.position)
            )
        )

    def get_for_user(self, user_id: UUID, document_id: UUID) -> UserAadhaarDocument | None:
        return self._db.scalar(
            select(UserAadhaarDocument).where(
                UserAadhaarDocument.id == document_id, UserAadhaarDocument.user_id == user_id
            )
        )

    def exists_for_user(self, user_id: UUID) -> bool:
        return bool(self._db.scalar(select(exists().where(UserAadhaarDocument.user_id == user_id))))

    def replace_all(
        self, existing: list[UserAadhaarDocument], documents: list[UserAadhaarDocument]
    ) -> list[UserAadhaarDocument]:
        try:
            for document in existing:
                self._db.delete(document)
            self._db.flush()
            self._db.add_all(documents)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        for document in documents:
            self._db.refresh(document)
        return documents
