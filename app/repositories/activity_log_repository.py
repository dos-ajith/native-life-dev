from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


class ActivityLogRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, activity_log: ActivityLog) -> ActivityLog:
        self._db.add(activity_log)
        self._db.commit()
        self._db.refresh(activity_log)
        return activity_log
