import os
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal, engine
from app.core.permissions import RoleName, RoleSlug
from app.core.security import hash_password
from app.core.timezone import app_now
from app.main import app
from app.models import Base
from app.models.role import Role
from app.models.user import User, UserStatus, UserType
from tests.conftest import TEST_SCHEMA

API = get_settings().api_v1_prefix
DEFAULT_PASSWORD = "Secret-pass-123"
DISPOSABLE_FLAG = "NATIVE_LIFE_DISPOSABLE_PG"
DISPOSABLE_DATABASE = "nl_concurrency_test"
DISPOSABLE_PORT = "55432"
DISPOSABLE_TIMEOUTS = "-c lock_timeout=5000 -c statement_timeout=15000"
REFUSED_EXIT_CODE = 3


def disposable_postgres_requested() -> bool:
    return os.environ.get(DISPOSABLE_FLAG) == "1"


def _query_values(url: URL, name: str) -> tuple[str, ...]:
    value = url.query.get(name)
    if value is None:
        return ()
    return value if isinstance(value, tuple) else (value,)


def _socket_directory_problems(url: URL) -> list[str]:
    hosts = _query_values(url, "host")
    if not hosts:
        return ["the URL has no absolute Unix socket directory (?host=/...)"]
    if len(hosts) > 1:
        return ["the URL repeats the host parameter"]
    if "," in hosts[0]:
        return ["the host parameter lists several hosts"]
    if not hosts[0].startswith("/"):
        return ["the URL has no absolute Unix socket directory (?host=/...)"]
    return []


def _socket_port_problems(url: URL) -> list[str]:
    if _query_values(url, "port") != (DISPOSABLE_PORT,):
        return [f"the URL must name exactly one socket port, {DISPOSABLE_PORT}"]
    return []


def _disposable_url_problems(url: URL) -> list[str]:
    problems = []
    if url.database != DISPOSABLE_DATABASE:
        problems.append(f"database is {url.database!r}, expected {DISPOSABLE_DATABASE!r}")
    if url.host or url.port:
        problems.append("the URL names a TCP host or port")
    return problems + _socket_directory_problems(url) + _socket_port_problems(url)


def _live_target_problems() -> list[str]:
    with engine.connect() as connection:
        database, port, over_socket, listen_addresses = connection.execute(
            text(
                "SELECT current_database(), current_setting('port'), "
                "inet_server_addr() IS NULL, current_setting('listen_addresses')"
            )
        ).one()
    problems = []
    if database != DISPOSABLE_DATABASE:
        problems.append(f"connected database is {database!r}")
    if port != DISPOSABLE_PORT:
        problems.append(f"server port is {port}")
    if not over_socket:
        problems.append("connection is not over a Unix socket")
    if listen_addresses != "":
        problems.append(f"server listens on TCP addresses {listen_addresses!r}")
    return problems


def _refuse(problems: list[str]) -> None:
    pytest.exit(
        "Refusing to run integration tests against a non-disposable database: "
        + "; ".join(problems),
        returncode=REFUSED_EXIT_CODE,
    )


def ensure_disposable_target() -> None:
    url_problems = _disposable_url_problems(engine.url)
    if url_problems:
        _refuse(url_problems)
    os.environ["PGOPTIONS"] = f"{os.environ.get('PGOPTIONS', '')} {DISPOSABLE_TIMEOUTS}".strip()
    engine.dispose()
    live_problems = _live_target_problems()
    if live_problems:
        _refuse(live_problems)


def _qualified_tables() -> str:
    return ", ".join(f'"{TEST_SCHEMA}"."{table.name}"' for table in Base.metadata.sorted_tables)


@pytest.fixture(scope="session", autouse=True)
def database_schema() -> Iterator[None]:
    if disposable_postgres_requested():
        ensure_disposable_target()
    assert TEST_SCHEMA.startswith("test_")
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{TEST_SCHEMA}"'))
        current = connection.execute(text("SELECT current_schema()")).scalar_one()
        assert current == TEST_SCHEMA, f"search_path not isolated: {current}"
        Base.metadata.create_all(connection, checkfirst=False)
    yield
    engine.dispose()
    with engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{TEST_SCHEMA}" CASCADE'))


@pytest.fixture(autouse=True)
def clean_database(database_schema: None) -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {_qualified_tables()} CASCADE"))
    with SessionLocal() as db:
        db.add_all(
            [
                Role(name=RoleName.INDIVIDUAL_USER, slug=RoleSlug.INDIVIDUAL_USER),
                Role(name=RoleName.SUPER_ADMIN, slug=RoleSlug.SUPER_ADMIN),
            ]
        )
        db.commit()
    yield


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


UserFactory = Callable[..., User]


@pytest.fixture
def make_user() -> UserFactory:
    counter = iter(range(1, 1_000_000))

    def factory(
        email: str | None = None,
        password: str | None = DEFAULT_PASSWORD,
        email_verified: bool = True,
        status: UserStatus = UserStatus.ACTIVE,
        user_type: UserType = UserType.PUBLIC,
        phone: str | None = None,
        phone_verified: bool = False,
        role_slug: str = RoleSlug.INDIVIDUAL_USER,
    ) -> User:
        number = next(counter)
        with SessionLocal() as session:
            role = session.query(Role).filter_by(slug=role_slug).one()
            user = User(
                first_name="Test",
                last_name=f"User{number}",
                email=email if email is not None else f"user{number}@example.com",
                password_hash=hash_password(password) if password is not None else None,
                status=status,
                user_type=user_type,
                email_verified_at=app_now().replace(tzinfo=None) if email_verified else None,
                phone=phone,
                phone_verified_at=app_now() if phone_verified else None,
                roles=[role],
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
            return user

    return factory


def login(
    client: TestClient, email: str, password: str = DEFAULT_PASSWORD, **extra: Any
) -> dict[str, Any]:
    response = client.post(
        f"{API}/auth/login", json={"email": email, "password": password, **extra}
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def refresh(client: TestClient, refresh_token: str) -> Any:
    return client.post(f"{API}/auth/refresh", json={"refresh_token": refresh_token})


def shift_session(db: Session, session_id: UUID | str, **columns: timedelta) -> None:
    assignments = ", ".join(f"{column} = {column} + :{column}" for column in columns)
    db.execute(
        text(f"UPDATE auth_sessions SET {assignments} WHERE id = :session_id"),
        {"session_id": str(session_id), **columns},
    )
    db.commit()
