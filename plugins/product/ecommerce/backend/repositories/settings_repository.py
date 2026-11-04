from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EcommerceSettings


class SettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, business_id: UUID) -> EcommerceSettings | None:
        return self._db.scalar(
            select(EcommerceSettings)
            .where(EcommerceSettings.business_id == business_id)
            .execution_options(populate_existing=True)
        )

    def add(self, settings: EcommerceSettings) -> EcommerceSettings:
        self._db.add(settings)
        self._db.flush()
        return settings
