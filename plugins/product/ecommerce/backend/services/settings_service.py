from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.plugins.sdk import ConflictError, User, record_activity

from ..activity_actions import EcommerceAction, EcommerceEntity
from ..config import DEFAULT_CURRENCY, DEFAULT_LOW_STOCK_THRESHOLD
from ..messages import EcommerceMessages
from ..models import EcommerceSettings
from ..repositories.settings_repository import SettingsRepository
from ..schemas.settings import SettingsRead, SettingsUpdate


class SettingsService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = SettingsRepository(db)

    def effective(self, business_id: UUID) -> tuple[str, int]:
        row = self._settings.get(business_id)
        if row is None:
            return DEFAULT_CURRENCY, DEFAULT_LOW_STOCK_THRESHOLD
        return row.currency, row.default_low_stock_threshold

    def get(self, business_id: UUID) -> SettingsRead:
        currency, threshold = self.effective(business_id)
        return SettingsRead(
            business_id=business_id, currency=currency, default_low_stock_threshold=threshold
        )

    def update(self, business_id: UUID, payload: SettingsUpdate, actor: User) -> SettingsRead:
        row = self._settings.get(business_id)
        if row is None:
            row = self._settings.add(
                EcommerceSettings(
                    business_id=business_id,
                    currency=DEFAULT_CURRENCY,
                    default_low_stock_threshold=DEFAULT_LOW_STOCK_THRESHOLD,
                )
            )
        if payload.currency is not None:
            row.currency = payload.currency
        if payload.default_low_stock_threshold is not None:
            row.default_low_stock_threshold = payload.default_low_stock_threshold
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ConflictError(EcommerceMessages.CONCURRENT_UPDATE) from exc
        record_activity(
            self._db,
            actor,
            EcommerceAction.SETTINGS_UPDATED,
            EcommerceEntity.SETTINGS,
            business_id,
            {"business_id": str(business_id)},
        )
        return self.get(business_id)
