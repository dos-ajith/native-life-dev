import queue
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg.errors
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.database import SessionLocal, engine
from app.core.exceptions import ConflictError
from app.core.messages import BusinessPluginMessages
from app.models.activity_log import ActivityLog
from app.models.business_plugin import BusinessPlugin, BusinessPluginStatus
from app.models.plugin import Plugin, PluginStatus
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.business_plugin_repository import BusinessPluginRepository
from app.services.business_plugin_service import BusinessPluginService
from tests.integration.conftest import API, disposable_postgres_requested
from tests.integration.plugins.conftest import (
    Actor,
    ActorFactory,
    PluginWorkspace,
    add_business,
    plugin_manifest,
    registry_for,
    set_plugin_status,
)

if not disposable_postgres_requested():
    pytest.skip(
        "requires NATIVE_LIFE_DISPOSABLE_PG=1 and the disposable PostgreSQL instance",
        allow_module_level=True,
    )

PLUGIN_KEY = "hotel"
HOTEL_CATEGORY = "business-service-hotel"
HOTEL = (
    f'{{ slug = "{HOTEL_CATEGORY}", name = "Hotel", parent = "business-service", '
    "bind = true, include_descendants = true }"
)
ROUNDS = 20
WAIT_SECONDS = 10
JOIN_SECONDS = 30
POLL_SECONDS = 0.02

INSERT_ROW = text(
    "INSERT INTO business_plugins (id, business_id, plugin_id, status, enabled_by) "
    "VALUES (:id, :business_id, :plugin_id, CAST(:status AS business_plugin_status), :enabled_by)"
)
LOCK_ROW = text(
    "SELECT id FROM business_plugins WHERE business_id = :business_id "
    "AND plugin_id = :plugin_id FOR UPDATE"
)
LOCK_ROW_NOWAIT = text("SELECT id FROM business_plugins WHERE id = :id FOR UPDATE NOWAIT")
WAIT_EVENT = text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid")


@dataclass(frozen=True)
class Snapshot:
    id: UUID
    status: BusinessPluginStatus
    enabled_by: UUID | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Scene:
    owner: Actor
    business_id: UUID
    plugin_id: UUID
    registry: PluginRegistry


def _snapshot(row: BusinessPlugin | None) -> Snapshot | None:
    if row is None:
        return None
    return Snapshot(row.id, row.status, row.enabled_by, row.created_at, row.updated_at)


class Worker:
    def __init__(self, task: Callable[[Session], Any]) -> None:
        self._task = task
        self._pids: queue.Queue[int] = queue.Queue()
        self.result: Any = None
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        with SessionLocal() as session:
            try:
                self._pids.put(session.scalar(select(func.pg_backend_pid())) or 0)
                self.result = self._task(session)
                session.commit()
            except BaseException as error:
                session.rollback()
                self.error = error

    def start(self) -> "Worker":
        self._thread.start()
        return self

    def backend_pid(self) -> int:
        return self._pids.get(timeout=WAIT_SECONDS)

    def join(self) -> "Worker":
        self._thread.join(timeout=JOIN_SECONDS)
        assert not self._thread.is_alive(), "worker did not finish"
        return self


def _wait_until_blocked_on_lock(pid: int) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            event = connection.execute(WAIT_EVENT, {"pid": pid}).scalar()
            connection.rollback()
            if event == "Lock":
                return
            time.sleep(POLL_SECONDS)
    pytest.fail(f"backend {pid} never waited on a lock")


@contextmanager
def _holder() -> Iterator[Connection]:
    connection = engine.connect()
    try:
        connection.begin()
        yield connection
    finally:
        if connection.in_transaction():
            connection.rollback()
        connection.close()


def _enable(scene: Scene, barrier: threading.Barrier | None = None) -> Callable[[Session], Any]:
    def task(session: Session) -> Snapshot | None:
        actor = session.get(User, scene.owner.user.id)
        assert actor is not None
        if barrier is not None:
            barrier.wait(timeout=WAIT_SECONDS)
        _, row = BusinessPluginService(session).enable(
            scene.business_id, PLUGIN_KEY, actor, scene.registry
        )
        return _snapshot(row)

    return task


def _disable(scene: Scene, barrier: threading.Barrier | None = None) -> Callable[[Session], Any]:
    def task(session: Session) -> Snapshot | None:
        actor = session.get(User, scene.owner.user.id)
        assert actor is not None
        if barrier is not None:
            barrier.wait(timeout=WAIT_SECONDS)
        _, row = BusinessPluginService(session).disable(scene.business_id, PLUGIN_KEY, actor)
        return _snapshot(row)

    return task


def _run_now(task: Callable[[Session], Any]) -> Any:
    worker = Worker(task).start().join()
    if worker.error is not None:
        raise worker.error
    return worker.result


def _rows(business_id: UUID) -> list[tuple[UUID, BusinessPluginStatus]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(BusinessPlugin.id, BusinessPlugin.status).where(
                BusinessPlugin.business_id == business_id
            )
        ).all()
        return [(row_id, status) for row_id, status in rows]


def _log_count(action: str) -> int:
    with SessionLocal() as session:
        return (
            session.scalar(
                select(func.count()).select_from(ActivityLog).where(ActivityLog.action == action)
            )
            or 0
        )


def _insert_uncommitted(holder: Connection, scene: Scene) -> UUID:
    row_id = uuid4()
    holder.execute(
        INSERT_ROW,
        {
            "id": row_id,
            "business_id": scene.business_id,
            "plugin_id": scene.plugin_id,
            "status": BusinessPluginStatus.ACTIVE.value,
            "enabled_by": scene.owner.user.id,
        },
    )
    return row_id


def _new_scene(scene: Scene) -> Scene:
    business = add_business(scene.owner.user, HOTEL_CATEGORY)
    return Scene(scene.owner, business.id, scene.plugin_id, scene.registry)


@pytest.fixture
def scene(
    client: TestClient,
    actor: ActorFactory,
    workspace: PluginWorkspace,
    use_registry: Callable[..., None],
) -> Scene:
    workspace.write(PLUGIN_KEY, plugin_manifest(PLUGIN_KEY, categories=f"[{HOTEL}]"))
    assert workspace.apply()[PLUGIN_KEY].outcome == "installed"
    set_plugin_status(PLUGIN_KEY, PluginStatus.ENABLED)
    use_registry(PLUGIN_KEY)
    owner = actor("provider")
    business = add_business(owner.user, HOTEL_CATEGORY)
    with SessionLocal() as session:
        plugin_id = session.scalar(select(Plugin.id).where(Plugin.key == PLUGIN_KEY))
    assert plugin_id is not None
    return Scene(owner, business.id, plugin_id, registry_for(PLUGIN_KEY))


def test_forced_first_insert_race_returns_the_winning_row(scene: Scene) -> None:
    with _holder() as holder:
        winner_id = _insert_uncommitted(holder, scene)
        worker = Worker(_enable(scene)).start()
        _wait_until_blocked_on_lock(worker.backend_pid())
        holder.commit()
    worker.join()
    assert worker.error is None
    assert worker.result.id == winner_id
    assert worker.result.status == BusinessPluginStatus.ACTIVE
    assert _rows(scene.business_id) == [(winner_id, BusinessPluginStatus.ACTIVE)]
    assert _log_count(ActivityAction.BUSINESS_PLUGIN_ENABLED) == 0


def test_concurrent_first_enables_create_one_row_and_one_audit_entry(scene: Scene) -> None:
    for round_number in range(ROUNDS):
        current = _new_scene(scene)
        barrier = threading.Barrier(2)
        workers = [Worker(_enable(current, barrier)).start() for _ in range(2)]
        for worker in workers:
            worker.join()
        assert [worker.error for worker in workers] == [None, None]
        results = [worker.result for worker in workers]
        assert results[0].id == results[1].id
        assert {result.status for result in results} == {BusinessPluginStatus.ACTIVE}
        assert _rows(current.business_id) == [(results[0].id, BusinessPluginStatus.ACTIVE)]
        assert _log_count(ActivityAction.BUSINESS_PLUGIN_ENABLED) == round_number + 1


def test_enable_and_disable_wait_for_a_locked_row_and_log_once(scene: Scene) -> None:
    _run_now(_enable(scene))
    for operation, expected, action in (
        (_disable, BusinessPluginStatus.DISABLED, ActivityAction.BUSINESS_PLUGIN_DISABLED),
        (_enable, BusinessPluginStatus.ACTIVE, ActivityAction.BUSINESS_PLUGIN_ENABLED),
    ):
        before = _log_count(action)
        with _holder() as holder:
            holder.execute(
                LOCK_ROW, {"business_id": scene.business_id, "plugin_id": scene.plugin_id}
            )
            worker = Worker(operation(scene)).start()
            _wait_until_blocked_on_lock(worker.backend_pid())
            holder.commit()
        worker.join()
        assert worker.error is None
        assert worker.result.status == expected
        assert _log_count(action) == before + 1


def test_a_change_committed_while_waiting_is_seen_and_not_logged_twice(scene: Scene) -> None:
    _run_now(_enable(scene))
    before = _log_count(ActivityAction.BUSINESS_PLUGIN_DISABLED)
    with _holder() as holder:
        holder.execute(LOCK_ROW, {"business_id": scene.business_id, "plugin_id": scene.plugin_id})
        holder.execute(
            text(
                "UPDATE business_plugins SET status = 'disabled' "
                "WHERE business_id = :business_id AND plugin_id = :plugin_id"
            ),
            {"business_id": scene.business_id, "plugin_id": scene.plugin_id},
        )
        worker = Worker(_disable(scene)).start()
        _wait_until_blocked_on_lock(worker.backend_pid())
        holder.commit()
    worker.join()
    assert worker.error is None
    assert worker.result.status == BusinessPluginStatus.DISABLED
    assert _log_count(ActivityAction.BUSINESS_PLUGIN_DISABLED) == before


def test_concurrent_enable_and_disable_keep_status_and_audit_consistent(scene: Scene) -> None:
    _run_now(_enable(scene))
    for _ in range(ROUNDS):
        enabled_before = _log_count(ActivityAction.BUSINESS_PLUGIN_ENABLED)
        disabled_before = _log_count(ActivityAction.BUSINESS_PLUGIN_DISABLED)
        barrier = threading.Barrier(2)
        workers = [
            Worker(_enable(scene, barrier)).start(),
            Worker(_disable(scene, barrier)).start(),
        ]
        for worker in workers:
            worker.join()
        assert [worker.error for worker in workers] == [None, None]
        [(_, status)] = _rows(scene.business_id)
        enabled_delta = _log_count(ActivityAction.BUSINESS_PLUGIN_ENABLED) - enabled_before
        disabled_delta = _log_count(ActivityAction.BUSINESS_PLUGIN_DISABLED) - disabled_before
        assert disabled_delta == 1
        assert enabled_delta == (1 if status == BusinessPluginStatus.ACTIVE else 0)
        if status == BusinessPluginStatus.DISABLED:
            _run_now(_enable(scene))


def test_disable_does_not_wait_for_an_uncommitted_first_enable(scene: Scene) -> None:
    with _holder() as holder:
        winner_id = _insert_uncommitted(holder, scene)
        worker = Worker(_disable(scene)).start().join()
        assert worker.error is None
        assert worker.result is None
        holder.commit()
    assert _rows(scene.business_id) == [(winner_id, BusinessPluginStatus.ACTIVE)]
    assert _log_count(ActivityAction.BUSINESS_PLUGIN_DISABLED) == 0


def test_insert_returns_enum_values_server_defaults_and_reloads(scene: Scene) -> None:
    with SessionLocal() as session:
        actor = session.get(User, scene.owner.user.id)
        assert actor is not None
        _, row = BusinessPluginService(session).enable(
            scene.business_id, PLUGIN_KEY, actor, scene.registry
        )
        assert isinstance(row.id, UUID)
        assert row.status == BusinessPluginStatus.ACTIVE
        assert row.enabled_by == scene.owner.user.id
        assert row.created_at is not None and row.updated_at is not None
        assert session.get(BusinessPlugin, row.id) is row
        with engine.connect() as connection:
            stored = connection.execute(
                text(
                    "SELECT status::text, pg_typeof(status)::text, enabled_by, created_at, "
                    "updated_at FROM business_plugins WHERE id = :id"
                ),
                {"id": row.id},
            ).one()
            assert tuple(stored) == (
                "active",
                "business_plugin_status",
                scene.owner.user.id,
                row.created_at,
                row.updated_at,
            )
            connection.execute(
                text("UPDATE business_plugins SET status = 'disabled' WHERE id = :id"),
                {"id": row.id},
            )
            connection.commit()
        session.commit()
        reloaded = BusinessPluginRepository(session).get_for_update(
            scene.business_id, scene.plugin_id
        )
        assert reloaded is row
        assert row.status == BusinessPluginStatus.DISABLED


def test_business_removed_during_enable_returns_409_without_rows_or_audit(
    scene: Scene, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    reached, release = threading.Event(), threading.Event()
    original = BusinessPluginRepository.add_if_absent

    def paused(
        self: BusinessPluginRepository, business_plugin: BusinessPlugin
    ) -> BusinessPlugin | None:
        reached.set()
        assert release.wait(WAIT_SECONDS)
        return original(self, business_plugin)

    monkeypatch.setattr(BusinessPluginRepository, "add_if_absent", paused)
    responses: list[Any] = []
    request = threading.Thread(
        target=lambda: responses.append(
            client.post(
                f"{API}/me/businesses/{scene.business_id}/plugins/{PLUGIN_KEY}",
                headers=scene.owner.headers,
            )
        ),
        daemon=True,
    )
    request.start()
    assert reached.wait(WAIT_SECONDS)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM businesses WHERE id = :id"), {"id": scene.business_id})
    release.set()
    request.join(timeout=JOIN_SECONDS)
    assert not request.is_alive()
    [response] = responses
    assert response.status_code == 409, response.text
    assert response.json() == {
        "success": False,
        "message": BusinessPluginMessages.ENABLE_TARGET_REMOVED,
        "errors": [],
    }
    assert _rows(scene.business_id) == []
    assert _log_count(ActivityAction.BUSINESS_PLUGIN_ENABLED) == 0


def test_winning_row_removed_before_reread_is_a_conflict(
    scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    reached, release = threading.Event(), threading.Event()
    original = BusinessPluginRepository.get_for_update
    calls: list[UUID] = []

    def paused(
        self: BusinessPluginRepository, business_id: UUID, plugin_id: UUID
    ) -> BusinessPlugin | None:
        calls.append(business_id)
        if len(calls) == 2:
            reached.set()
            assert release.wait(WAIT_SECONDS)
        return original(self, business_id, plugin_id)

    monkeypatch.setattr(BusinessPluginRepository, "get_for_update", paused)
    with _holder() as holder:
        winner_id = _insert_uncommitted(holder, scene)
        worker = Worker(_enable(scene)).start()
        _wait_until_blocked_on_lock(worker.backend_pid())
        holder.commit()
    assert reached.wait(WAIT_SECONDS)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM business_plugins WHERE id = :id"), {"id": winner_id})
    release.set()
    worker.join()
    assert isinstance(worker.error, ConflictError)
    assert worker.error.message == BusinessPluginMessages.ENABLE_CONFLICT
    assert worker.error.status_code == 409
    assert _rows(scene.business_id) == []
    assert _log_count(ActivityAction.BUSINESS_PLUGIN_ENABLED) == 0


def _nowait_lock(row_id: UUID) -> None:
    with _holder() as holder:
        holder.execute(LOCK_ROW_NOWAIT, {"id": row_id})


def test_already_active_enable_holds_the_row_lock_until_commit(scene: Scene) -> None:
    row_id = _run_now(_enable(scene)).id
    with SessionLocal() as session:
        actor = session.get(User, scene.owner.user.id)
        assert actor is not None
        _, row = BusinessPluginService(session).enable(
            scene.business_id, PLUGIN_KEY, actor, scene.registry
        )
        assert row.id == row_id
        with pytest.raises(OperationalError) as locked:
            _nowait_lock(row_id)
        assert isinstance(locked.value.orig, psycopg.errors.LockNotAvailable)
        session.commit()
        _nowait_lock(row_id)


def test_completed_http_request_releases_the_row_lock(scene: Scene, client: TestClient) -> None:
    row_id = _run_now(_enable(scene)).id
    response = client.post(
        f"{API}/me/businesses/{scene.business_id}/plugins/{PLUGIN_KEY}",
        headers=scene.owner.headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "active"
    _nowait_lock(row_id)


def test_fresh_insert_does_not_keep_the_row_lock(scene: Scene) -> None:
    with SessionLocal() as session:
        actor = session.get(User, scene.owner.user.id)
        assert actor is not None
        _, row = BusinessPluginService(session).enable(
            scene.business_id, PLUGIN_KEY, actor, scene.registry
        )
        _nowait_lock(row.id)
    assert _log_count(ActivityAction.BUSINESS_PLUGIN_ENABLED) == 1
