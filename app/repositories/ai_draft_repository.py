from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.ai_draft import AIDraft, AIDraftKind


class AIDraftRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, user_id: UUID, kind: AIDraftKind) -> AIDraft | None:
        return self._db.scalar(
            select(AIDraft).where(AIDraft.user_id == user_id, AIDraft.kind == kind)
        )

    def upsert(self, user_id: UUID, kind: AIDraftKind, details: dict[str, Any]) -> AIDraft:
        statement = (
            pg_insert(AIDraft)
            .values(user_id=user_id, kind=kind, details=details)
            .on_conflict_do_update(
                index_elements=[AIDraft.user_id, AIDraft.kind],
                set_={"details": details, "updated_at": func.now()},
            )
            .returning(AIDraft.id)
        )
        draft_id = self._db.scalar(statement)
        self._db.commit()
        return self._db.get_one(AIDraft, draft_id, populate_existing=True)

    def delete(self, user_id: UUID, kind: AIDraftKind) -> bool:
        deleted_id = self._db.scalar(
            delete(AIDraft)
            .where(AIDraft.user_id == user_id, AIDraft.kind == kind)
            .returning(AIDraft.id)
        )
        self._db.commit()
        return deleted_id is not None

    def delete_stale(self, user_id: UUID, kind: AIDraftKind, max_age: timedelta) -> bool:
        deleted_id = self._db.scalar(
            delete(AIDraft)
            .where(
                AIDraft.user_id == user_id,
                AIDraft.kind == kind,
                AIDraft.updated_at < func.now() - max_age,
            )
            .returning(AIDraft.id)
        )
        self._db.commit()
        return deleted_id is not None
