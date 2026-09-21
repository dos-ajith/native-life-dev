from sqlalchemy.orm import Session

from app.models.post_share import PostShare


class PostShareRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, share: PostShare) -> PostShare:
        self._db.add(share)
        self._db.commit()
        self._db.refresh(share)
        return share
