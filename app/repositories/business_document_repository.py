from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_document import BusinessDocument


class BusinessDocumentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, document_id: UUID) -> BusinessDocument | None:
        return self._db.get(BusinessDocument, document_id)

    def list_by_business(self, business_id: UUID) -> list[BusinessDocument]:
        return list(
            self._db.scalars(
                select(BusinessDocument)
                .where(BusinessDocument.business_id == business_id)
                .order_by(BusinessDocument.created_at.asc(), BusinessDocument.id.asc())
            )
        )

    def add(self, document: BusinessDocument) -> BusinessDocument:
        self._db.add(document)
        self._db.commit()
        self._db.refresh(document)
        return document

    def save(self, document: BusinessDocument) -> BusinessDocument:
        self._db.commit()
        self._db.refresh(document)
        return document

    def delete(self, document: BusinessDocument) -> None:
        self._db.delete(document)
        self._db.commit()
