import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import make_url

from tests.integration import conftest as guard

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONCURRENCY_MODULE = "tests/integration/plugins/test_business_plugin_concurrency.py"
VALID_URL = "postgresql+psycopg://nl_test@/nl_concurrency_test?host=/tmp/nlpg.abc123&port=55432"
UNREACHABLE_DEV_URL = (
    "postgresql+psycopg://nobody@/nativelife_dev?host=/nonexistent-nl-guard&port=5432"
)
UNREACHABLE_REPEATED_HOST_PORTS_URL = (
    "postgresql+psycopg://nl_test@/nl_concurrency_test"
    "?host=/nonexistent-nl-guard-a:55432&host=/nonexistent-nl-guard-b:55432"
)
UNREACHABLE_COMMA_HOSTS_URL = (
    "postgresql+psycopg://nl_test@/nl_concurrency_test"
    "?host=/nonexistent-nl-guard-a,/nonexistent-nl-guard-b&port=55432,55432"
)
UNBUILDABLE_MULTIHOST_URLS = [
    "postgresql+psycopg://nl_test@/nl_concurrency_test"
    "?host=/nonexistent-nl-guard-a&host=/nonexistent-nl-guard-b&port=55432",
    "postgresql+psycopg://nl_test@/nl_concurrency_test"
    "?host=/nonexistent-nl-guard-a,/nonexistent-nl-guard-b&port=55432",
]
CHILD_TIMEOUT_SECONDS = 180
LIVE_OK = ("nl_concurrency_test", "55432", True, "")


@pytest.mark.parametrize(
    ("label", "url", "expected"),
    [
        ("valid disposable url", VALID_URL, []),
        (
            "repeated host parameters",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a&host=/tmp/b&port=55432",
            ["repeats the host parameter"],
        ),
        (
            "comma-separated hosts",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a,/tmp/b&port=55432",
            ["lists several hosts"],
        ),
        (
            "comma-separated hosts, second one relative",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a,tmp/b&port=55432",
            ["lists several hosts"],
        ),
        (
            "repeated hosts that carry their own ports",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a:55432&host=/tmp/b:55432",
            ["repeats the host parameter", "exactly one socket port"],
        ),
        (
            "comma-separated hosts with matching comma-separated ports",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a,/tmp/b&port=55432,55432",
            ["lists several hosts", "exactly one socket port"],
        ),
        (
            "repeated port parameters",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a&port=55432&port=5432",
            ["exactly one socket port"],
        ),
        (
            "comma-separated ports",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a&port=55432,5432",
            ["exactly one socket port"],
        ),
        (
            "tcp host",
            "postgresql+psycopg://u@localhost:55432/nl_concurrency_test",
            ["TCP host or port", "no absolute Unix socket directory", "exactly one socket port"],
        ),
        (
            "tcp host on the development port",
            "postgresql+psycopg://u@localhost:5432/nativelife_dev",
            ["expected 'nl_concurrency_test'", "TCP host or port"],
        ),
        (
            "development port over a socket",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a&port=5432",
            ["exactly one socket port"],
        ),
        (
            "missing socket path",
            "postgresql+psycopg://u@/nl_concurrency_test?port=55432",
            ["no absolute Unix socket directory"],
        ),
        (
            "relative socket path",
            "postgresql+psycopg://u@/nl_concurrency_test?host=tmp/a&port=55432",
            ["no absolute Unix socket directory"],
        ),
        (
            "missing port",
            "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a",
            ["exactly one socket port"],
        ),
        (
            "wrong database over a valid socket",
            "postgresql+psycopg://u@/nativelife_dev?host=/tmp/a&port=55432",
            ["expected 'nl_concurrency_test'"],
        ),
        (
            "no database",
            "postgresql+psycopg://u@/?host=/tmp/a&port=55432",
            ["expected 'nl_concurrency_test'"],
        ),
    ],
)
def test_disposable_url_rules(label: str, url: str, expected: list[str]) -> None:
    problems = guard._disposable_url_problems(make_url(url))
    if not expected:
        assert problems == [], label
        return
    assert problems, label
    for fragment in expected:
        assert any(fragment in problem for problem in problems), (label, fragment, problems)


class FakeResult:
    def __init__(self, row: tuple[Any, ...]) -> None:
        self._row = row

    def one(self) -> tuple[Any, ...]:
        return self._row


class FakeConnection:
    def __init__(self, row: tuple[Any, ...]) -> None:
        self._row = row

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute(self, *_args: object) -> FakeResult:
        return FakeResult(self._row)


class FakeEngine:
    def __init__(self, url: str, live_row: tuple[Any, ...] = LIVE_OK) -> None:
        self.url = make_url(url)
        self.calls: list[str] = []
        self._live_row = live_row

    def dispose(self) -> None:
        self.calls.append("dispose")

    def connect(self) -> FakeConnection:
        self.calls.append("connect")
        return FakeConnection(self._live_row)

    def begin(self) -> None:
        self.calls.append("begin")
        raise AssertionError("the guard must not open a writing transaction")


@pytest.fixture
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setenv("PGOPTIONS", "-c search_path=test_probe,public")
    return monkeypatch


def _install(monkeypatch: pytest.MonkeyPatch, engine: FakeEngine) -> FakeEngine:
    monkeypatch.setattr(guard, "engine", engine)
    return engine


@pytest.mark.parametrize(
    "url",
    [
        UNREACHABLE_DEV_URL,
        "postgresql+psycopg://u@localhost:5432/nativelife_dev",
        "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a&host=/tmp/b&port=55432",
        "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a,/tmp/b&port=55432",
        "postgresql+psycopg://u@/nl_concurrency_test?host=/tmp/a&port=55432&port=5432",
        "postgresql+psycopg://u@localhost:55432/nl_concurrency_test",
        "postgresql+psycopg://u@/nl_concurrency_test?port=55432",
    ],
)
def test_invalid_urls_are_refused_before_any_connection(
    isolated_environment: pytest.MonkeyPatch, url: str
) -> None:
    engine = _install(isolated_environment, FakeEngine(url))
    with pytest.raises(pytest.exit.Exception) as refused:
        guard.ensure_disposable_target()
    assert refused.value.returncode == guard.REFUSED_EXIT_CODE
    assert "Refusing to run integration tests" in str(refused.value)
    assert engine.calls == []
    assert os.environ["PGOPTIONS"] == "-c search_path=test_probe,public"


@pytest.mark.parametrize(
    ("live_row", "fragment"),
    [
        (("nativelife_dev", "55432", True, ""), "connected database is 'nativelife_dev'"),
        (("nl_concurrency_test", "5432", True, ""), "server port is 5432"),
        (("nl_concurrency_test", "55432", False, ""), "not over a Unix socket"),
        (("nl_concurrency_test", "55432", True, "localhost"), "listens on TCP addresses"),
        (("nativelife_dev", "5432", False, "localhost"), "connected database"),
    ],
)
def test_a_valid_url_pointing_at_the_wrong_live_server_is_refused(
    isolated_environment: pytest.MonkeyPatch, live_row: tuple[Any, ...], fragment: str
) -> None:
    engine = _install(isolated_environment, FakeEngine(VALID_URL, live_row))
    with pytest.raises(pytest.exit.Exception) as refused:
        guard.ensure_disposable_target()
    assert refused.value.returncode == guard.REFUSED_EXIT_CODE
    assert fragment in str(refused.value)
    assert engine.calls == ["dispose", "connect"]


def test_a_verified_target_is_accepted_and_gets_safety_timeouts(
    isolated_environment: pytest.MonkeyPatch,
) -> None:
    engine = _install(isolated_environment, FakeEngine(VALID_URL))
    guard.ensure_disposable_target()
    assert engine.calls == ["dispose", "connect"]
    assert os.environ["PGOPTIONS"] == (
        "-c search_path=test_probe,public -c lock_timeout=5000 -c statement_timeout=15000"
    )


def test_the_flag_is_required_for_the_guard_to_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(guard.DISPOSABLE_FLAG, raising=False)
    assert guard.disposable_postgres_requested() is False
    for value in ("0", "true", "yes", ""):
        monkeypatch.setenv(guard.DISPOSABLE_FLAG, value)
        assert guard.disposable_postgres_requested() is False
    monkeypatch.setenv(guard.DISPOSABLE_FLAG, "1")
    assert guard.disposable_postgres_requested() is True


def _run_child(database_url: str, flag: str | None) -> subprocess.CompletedProcess[str]:
    environment = {key: value for key, value in os.environ.items() if key != guard.DISPOSABLE_FLAG}
    environment["DATABASE_URL"] = database_url
    if flag is not None:
        environment[guard.DISPOSABLE_FLAG] = flag
    return subprocess.run(
        [sys.executable, "-m", "pytest", CONCURRENCY_MODULE, "-q", "-p", "no:cacheprovider", "-rs"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT_SECONDS,
        check=False,
    )


@pytest.mark.parametrize(
    "url",
    [UNREACHABLE_DEV_URL, UNREACHABLE_REPEATED_HOST_PORTS_URL, UNREACHABLE_COMMA_HOSTS_URL],
)
def test_pytest_exits_before_any_fixture_touches_a_refused_target(url: str) -> None:
    completed = _run_child(url, flag="1")
    output = completed.stdout + completed.stderr
    assert completed.returncode == guard.REFUSED_EXIT_CODE, output
    assert "Refusing to run integration tests against a non-disposable database" in output
    assert "no tests ran" in output
    assert "OperationalError" not in output and "connection" not in output.lower()


@pytest.mark.parametrize("url", UNBUILDABLE_MULTIHOST_URLS)
def test_multihost_urls_the_driver_cannot_build_fail_before_any_fixture(url: str) -> None:
    completed = _run_child(url, flag="1")
    output = completed.stdout + completed.stderr
    assert completed.returncode in (guard.REFUSED_EXIT_CODE, pytest.ExitCode.USAGE_ERROR), output
    assert "passed" not in output and "OperationalError" not in output


def test_without_the_flag_the_concurrency_module_is_skipped_without_fixtures() -> None:
    completed = _run_child(UNREACHABLE_DEV_URL, flag=None)
    output = completed.stdout + completed.stderr
    assert completed.returncode in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED), output
    assert "1 skipped" in output
    assert "requires NATIVE_LIFE_DISPOSABLE_PG=1" in output
