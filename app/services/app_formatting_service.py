from sqlalchemy.orm import Session

from app.core.formatting_context import (
    APP_DATE_FORMAT_SETTING_KEY,
    APP_TIME_FORMAT_SETTING_KEY,
    set_datetime_formats,
)
from app.repositories.setting_repository import SettingRepository


def refresh_datetime_formats(db: Session) -> None:
    settings = SettingRepository(db)
    date_setting = settings.get_by_key(APP_DATE_FORMAT_SETTING_KEY)
    time_setting = settings.get_by_key(APP_TIME_FORMAT_SETTING_KEY)
    set_datetime_formats(
        date_setting.value if date_setting else None,
        time_setting.value if time_setting else None,
    )
