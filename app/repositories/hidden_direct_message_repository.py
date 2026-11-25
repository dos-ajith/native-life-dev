from uuid import UUID

from sqlalchemy.orm import Session

from app.models.hidden_direct_message import HiddenDirectMessage


class HiddenDirectMessageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, message_id: UUID, user_id: UUID) -> HiddenDirectMessage:
        hidden = HiddenDirectMessage(message_id=message_id, user_id=user_id)
        self._db.add(hidden)
        self._db.commit()
        self._db.refresh(hidden)
        return hidden
