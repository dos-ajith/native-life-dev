from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.device_token import DevicePlatform, DeviceToken


class DeviceTokenRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_token(self, token: str) -> DeviceToken | None:
        return self._db.scalar(select(DeviceToken).where(DeviceToken.token == token))

    def upsert(self, user_id: UUID, token: str, platform: DevicePlatform) -> DeviceToken:
        statement = (
            pg_insert(DeviceToken)
            .values(user_id=user_id, token=token, platform=platform)
            .on_conflict_do_update(
                index_elements=[DeviceToken.token],
                set_={"user_id": user_id, "platform": platform, "updated_at": func.now()},
            )
            .returning(DeviceToken.id)
        )
        device_id = self._db.scalar(statement)
        self._db.commit()
        return self._db.get_one(DeviceToken, device_id, populate_existing=True)

    def delete_for_user(self, user_id: UUID, token: str) -> DeviceToken | None:
        device = self._db.scalar(
            select(DeviceToken).where(DeviceToken.user_id == user_id, DeviceToken.token == token)
        )
        if device is None:
            return None
        self._db.delete(device)
        self._db.commit()
        return device

    def list_tokens_for_user(self, user_id: UUID) -> list[str]:
        return list(
            self._db.scalars(
                select(DeviceToken.token)
                .where(DeviceToken.user_id == user_id)
                .order_by(DeviceToken.updated_at.desc())
            )
        )

    def delete_by_tokens(self, tokens: Sequence[str]) -> None:
        if not tokens:
            return
        self._db.execute(delete(DeviceToken).where(DeviceToken.token.in_(tokens)))
        self._db.commit()
