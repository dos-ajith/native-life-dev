from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, or_, select, union_all
from sqlalchemy.orm import Session

from app.schemas.community_timeline import TimelineItemType


@dataclass(frozen=True)
class TimelineEntry:
    id: UUID
    sort_at: datetime
    type: TimelineItemType


class CommunityTimelineRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def page(
        self, sources: list[Select[*tuple[Any, ...]]], before: TimelineEntry | None, limit: int
    ) -> list[TimelineEntry]:
        merged = union_all(*sources).subquery()
        query = select(merged.c.id, merged.c.sort_at, merged.c.kind)
        if before is not None:
            query = query.where(
                or_(
                    merged.c.sort_at < before.sort_at,
                    and_(merged.c.sort_at == before.sort_at, merged.c.id < before.id),
                )
            )
        rows = self._db.execute(
            query.order_by(merged.c.sort_at.desc(), merged.c.id.desc()).limit(limit)
        ).all()
        return [
            TimelineEntry(id=row.id, sort_at=row.sort_at, type=TimelineItemType(row.kind))
            for row in rows
        ]
