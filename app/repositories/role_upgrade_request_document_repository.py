from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role_upgrade_request_document import RoleUpgradeRequestDocument


class RoleUpgradeRequestDocumentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, document_id: UUID) -> RoleUpgradeRequestDocument | None:
        return self._db.get(RoleUpgradeRequestDocument, document_id)

    def list_by_request(self, request_id: UUID) -> list[RoleUpgradeRequestDocument]:
        return list(
            self._db.scalars(
                select(RoleUpgradeRequestDocument)
                .where(RoleUpgradeRequestDocument.request_id == request_id)
                .order_by(RoleUpgradeRequestDocument.created_at)
            )
        )

    def add(self, document: RoleUpgradeRequestDocument) -> RoleUpgradeRequestDocument:
        self._db.add(document)
        self._db.commit()
        self._db.refresh(document)
        return document
