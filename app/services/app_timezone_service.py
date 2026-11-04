from sqlalchemy.orm import Session

from app.core.timezone import APP_TIMEZONE_SETTING_KEY, set_app_timezone
from app.repositories.setting_repository import SettingRepository


def refresh_app_timezone(db: Session) -> None:
    setting = SettingRepository(db).get_by_key(APP_TIMEZONE_SETTING_KEY)
    set_app_timezone(setting.value if setting else None)
