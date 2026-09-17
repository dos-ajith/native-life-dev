from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.active_token import ActiveToken
from app.repositories.active_token_repository import ActiveTokenRepository


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_activate_then_deactivate(db: Session) -> None:
    repository = ActiveTokenRepository(db)
    jti = uuid4()

    repository.activate(jti, datetime.now(UTC) + timedelta(minutes=30))
    db.commit()
    assert repository.is_active(jti) is True

    repository.deactivate(jti)
    db.commit()
    assert repository.is_active(jti) is False


def test_is_active_rejects_expired_row_even_if_not_yet_pruned(db: Session) -> None:
    jti = uuid4()
    db.add(ActiveToken(jti=jti, expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    db.commit()

    try:
        assert ActiveTokenRepository(db).is_active(jti) is False
    finally:
        db.execute(delete(ActiveToken).where(ActiveToken.jti == jti))
        db.commit()


def test_activate_prunes_already_expired_rows(db: Session) -> None:
    repository = ActiveTokenRepository(db)
    expired_jti = uuid4()
    db.add(ActiveToken(jti=expired_jti, expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    db.commit()

    new_jti = uuid4()
    repository.activate(new_jti, datetime.now(UTC) + timedelta(minutes=30))
    db.commit()

    try:
        assert repository.is_active(expired_jti) is False
        assert repository.is_active(new_jti) is True
    finally:
        db.execute(delete(ActiveToken).where(ActiveToken.jti == new_jti))
        db.commit()
