from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.email_verification_otp import EmailVerificationOtp


class EmailVerificationOtpRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, user_id: UUID, otp_hash: str, expires_at: datetime) -> EmailVerificationOtp:
        otp = EmailVerificationOtp(user_id=user_id, otp_hash=otp_hash, expires_at=expires_at)
        self._db.add(otp)
        self._db.commit()
        self._db.refresh(otp)
        return otp

    def get_latest_for_user(self, user_id: UUID) -> EmailVerificationOtp | None:
        return self._db.scalar(
            select(EmailVerificationOtp)
            .where(EmailVerificationOtp.user_id == user_id)
            .order_by(EmailVerificationOtp.created_at.desc())
            .limit(1)
        )

    def get_latest_active_for_update(self, user_id: UUID) -> EmailVerificationOtp | None:
        return self._db.scalar(
            select(EmailVerificationOtp)
            .where(
                EmailVerificationOtp.user_id == user_id,
                EmailVerificationOtp.consumed_at.is_(None),
            )
            .order_by(EmailVerificationOtp.created_at.desc())
            .limit(1)
            .with_for_update()
        )

    def invalidate_active_for_user(self, user_id: UUID) -> None:
        self._db.execute(
            update(EmailVerificationOtp)
            .where(
                EmailVerificationOtp.user_id == user_id,
                EmailVerificationOtp.consumed_at.is_(None),
            )
            .values(consumed_at=datetime.now(UTC))
        )
        self._db.commit()

    def increment_attempts(self, otp: EmailVerificationOtp) -> None:
        otp.attempts += 1
        self._db.commit()

    def delete_all_for_user(self, user_id: UUID) -> None:
        self._db.execute(
            delete(EmailVerificationOtp).where(EmailVerificationOtp.user_id == user_id)
        )
