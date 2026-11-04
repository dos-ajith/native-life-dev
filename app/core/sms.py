import logging
from dataclasses import dataclass
from typing import Protocol

from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

from app.core.config import Settings
from app.utils.phone import mask_phone

logger = logging.getLogger(__name__)

TWILIO_HTTP_LOGGER_NAME = "app.sms.twilio_http"


@dataclass(frozen=True)
class OutgoingSms:
    to_phone: str
    body: str


@dataclass(frozen=True)
class SmsSendResult:
    success: bool
    provider_message_id: str | None = None
    error_code: str | None = None


class SmsProvider(Protocol):
    name: str

    def send(self, message: OutgoingSms) -> SmsSendResult: ...


class ConsoleSmsProvider:
    name: str = "console"

    def send(self, message: OutgoingSms) -> SmsSendResult:
        logger.warning(
            "[DEV ONLY, never enabled in production] SMS to %s: %s",
            mask_phone(message.to_phone),
            message.body,
        )
        return SmsSendResult(success=True)


class TwilioSmsProvider:
    name: str = "twilio"

    def __init__(self, client: Client, from_number: str) -> None:
        self._client = client
        self._from_number = from_number

    @classmethod
    def from_settings(cls, settings: Settings) -> "TwilioSmsProvider":
        if (
            settings.twilio_account_sid is None
            or settings.twilio_api_key_sid is None
            or settings.twilio_api_key_secret is None
            or settings.twilio_from_number is None
        ):
            raise ValueError("Twilio SMS provider is not configured")
        http_logger = logging.getLogger(TWILIO_HTTP_LOGGER_NAME)
        http_logger.setLevel(logging.WARNING)
        client = Client(
            username=settings.twilio_api_key_sid,
            password=settings.twilio_api_key_secret.get_secret_value(),
            account_sid=settings.twilio_account_sid,
            http_client=TwilioHttpClient(
                timeout=settings.twilio_request_timeout_seconds, logger=http_logger
            ),
        )
        return cls(client, settings.twilio_from_number)

    def send(self, message: OutgoingSms) -> SmsSendResult:
        masked = mask_phone(message.to_phone)
        try:
            sent = self._client.messages.create(
                to=message.to_phone, from_=self._from_number, body=message.body
            )
        except TwilioRestException as exc:
            logger.warning(
                "Twilio rejected SMS to %s: status=%s code=%s", masked, exc.status, exc.code
            )
            return SmsSendResult(success=False, error_code=str(exc.code or exc.status))
        except (TwilioException, OSError) as exc:
            logger.warning("Twilio unreachable for SMS to %s: %s", masked, type(exc).__name__)
            return SmsSendResult(success=False, error_code=type(exc).__name__)
        logger.info("Twilio accepted SMS to %s: sid=%s", masked, sent.sid)
        return SmsSendResult(success=True, provider_message_id=sent.sid)


def get_sms_provider(settings: Settings) -> SmsProvider | None:
    if settings.sms_provider == "console":
        return ConsoleSmsProvider()
    if settings.sms_provider == "twilio":
        return TwilioSmsProvider.from_settings(settings)
    return None
