from datetime import datetime, time, timedelta

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.user import User
from app.schemas.activity_log import ActivityLogQuery
from app.schemas.pagination import PaginationParams

ONE_DAY = timedelta(days=1)


def _filters(query: ActivityLogQuery) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if query.action is not None:
        filters.append(ActivityLog.action == query.action)
    if query.user_id is not None:
        filters.append(ActivityLog.user_id == query.user_id)
    if query.entity_type is not None:
        filters.append(ActivityLog.entity_type == query.entity_type)
    if query.entity_id is not None:
        filters.append(ActivityLog.entity_id == query.entity_id)
    if query.date_from is not None:
        filters.append(ActivityLog.created_at >= datetime.combine(query.date_from, time.min))
    if query.date_to is not None:
        filters.append(ActivityLog.created_at < datetime.combine(query.date_to + ONE_DAY, time.min))
    return filters


class ActivityLogRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, activity_log: ActivityLog) -> ActivityLog:
        self._db.add(activity_log)
        self._db.commit()
        self._db.refresh(activity_log)
        return activity_log

    def page(
        self, query: ActivityLogQuery, params: PaginationParams
    ) -> tuple[list[tuple[ActivityLog, User | None]], int]:
        filters = _filters(query)
        total = self._db.scalar(select(func.count()).select_from(ActivityLog).where(*filters)) or 0
        rows = self._db.execute(
            select(ActivityLog, User)
            .outerjoin(User, User.id == ActivityLog.user_id)
            .where(*filters)
            .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        ).all()
        return [(log, actor) for log, actor in rows], total
