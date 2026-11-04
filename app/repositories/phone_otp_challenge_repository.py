from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.timezone import app_now
from app.models.phone_otp_challenge import PhoneOtpChallenge


class PhoneOtpChallengeRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def lock_phone(self, phone: str) -> None:
        self._db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(phone, 0))))

    def remaining_cooldown_seconds(self, phone: str, window: timedelta) -> int:
        remaining = self._db.scalar(
            select(
                func.ceil(func.extract("epoch", PhoneOtpChallenge.created_at + window - func.now()))
            )
            .where(
                PhoneOtpChallenge.phone == phone,
                PhoneOtpChallenge.created_at > func.now() - window,
            )
            .order_by(PhoneOtpChallenge.created_at.desc())
            .limit(1)
        )
        return int(remaining or 0)

    def count_for_phone_since(self, phone: str, window: timedelta) -> int:
        return self._db.scalar(
            select(func.count()).where(
                PhoneOtpChallenge.phone == phone,
                PhoneOtpChallenge.created_at > func.now() - window,
            )
        ) or 0

    def count_for_ip_since(self, ip_address: str, window: timedelta) -> int:
        return self._db.scalar(
            select(func.count()).where(
                PhoneOtpChallenge.ip_address == ip_address,
                PhoneOtpChallenge.created_at > func.now() - window,
            )
        ) or 0

    def invalidate_active(self, phone: str) -> None:
        self._db.execute(
            update(PhoneOtpChallenge)
            .where(PhoneOtpChallenge.phone == phone, PhoneOtpChallenge.consumed_at.is_(None))
            .values(consumed_at=app_now())
        )

    def add(self, challenge: PhoneOtpChallenge) -> None:
        self._db.add(challenge)
        self._db.flush()

    def get_latest_active_for_update(self, phone: str) -> PhoneOtpChallenge | None:
        return self._db.scalar(
            select(PhoneOtpChallenge)
            .where(PhoneOtpChallenge.phone == phone, PhoneOtpChallenge.consumed_at.is_(None))
            .order_by(PhoneOtpChallenge.created_at.desc())
            .limit(1)
            .with_for_update()
        )
