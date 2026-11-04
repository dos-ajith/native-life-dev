from app.core.config import Settings
from app.schemas.device_token import FirebaseWebConfigRead, WebPushConfigRead


class WebPushConfigService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get(self) -> WebPushConfigRead:
        settings = self._settings
        required = (
            settings.fcm_project_id,
            settings.fcm_web_api_key,
            settings.fcm_web_messaging_sender_id,
            settings.fcm_web_app_id,
            settings.fcm_web_vapid_key,
        )
        if settings.push_provider != "fcm" or not all(required):
            return WebPushConfigRead(enabled=False)
        return WebPushConfigRead(
            enabled=True,
            firebase_config=FirebaseWebConfigRead(
                apiKey=str(settings.fcm_web_api_key),
                authDomain=settings.fcm_web_auth_domain,
                projectId=str(settings.fcm_project_id),
                storageBucket=settings.fcm_web_storage_bucket,
                messagingSenderId=str(settings.fcm_web_messaging_sender_id),
                appId=str(settings.fcm_web_app_id),
            ),
            vapid_key=settings.fcm_web_vapid_key,
        )
