from datetime import datetime

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.timezone import app_now, to_naive_app_time
from app.realtime.publisher import RealtimePublisher
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_repository import DealRepository
from app.services.activity_log_service import ActivityLogService
from app.services.notification_service import NotificationService

ENTITY_TYPE = "deal"


def deal_clock_now() -> datetime:
    return to_naive_app_time(app_now())


class DealExpiryService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._db = db
        self._deals = DealRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._notifications = NotificationService(db, publisher)
        self._activity_logs = ActivityLogService(db)

    def expire_overdue(self) -> int:
        expired = self._deals.expire_overdue(deal_clock_now())
        self._invitations.close_open([deal.id for deal in expired])
        self._db.commit()
        for deal in expired:
            self._activity_logs.log(
                actor=None,
                action=ActivityAction.DEAL_EXPIRED,
                entity_type=ENTITY_TYPE,
                entity_id=deal.id,
            )
            self._notifications.notify_deal_expired(deal.created_by, deal.id, deal.name)
        return len(expired)
