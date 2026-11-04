import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.plugins.errors import PluginError
from app.plugins.smoke import run_smoke_load
from tests.unit.plugins.conftest import REFERENCE_PLUGIN_ROOT, PluginWriter


def _cli(*args: str, plugins_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if plugins_dir is not None:
        env["PLUGINS_DIR"] = str(plugins_dir)
    return subprocess.run(
        [sys.executable, "-m", "app.plugins.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


def test_validate_accepts_the_repository_plugins() -> None:
    completed = _cli("validate")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "ok      hello 1.1.0" in completed.stdout


def test_validate_reports_failures_with_a_non_zero_exit(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("ecommerce", dependencies='[{ key = "catalog", version = ">=1.0" }]')
    completed = _cli("validate", plugins_dir=plugins_dir)
    assert completed.returncode == 1
    assert "'catalog' is not available" in completed.stdout


def test_smoke_load_of_the_reference_plugin_succeeds_in_a_subprocess() -> None:
    run_smoke_load(REFERENCE_PLUGIN_ROOT)


def test_smoke_load_failure_is_contained_in_the_subprocess(write_plugin: PluginWriter) -> None:
    root = write_plugin("crashes", plugin_code="raise SystemExit('crashed during import')\n")
    with pytest.raises(PluginError, match="Smoke load in a separate process failed"):
        run_smoke_load(root)


def test_subclassing_a_core_model_is_rejected_in_the_smoke_subprocess(
    write_plugin: PluginWriter,
) -> None:
    root = write_plugin(
        "evil",
        plugin_code="""
        from app.plugins.sdk import User

        class SneakyUser(User):
            pass

        def register(ctx):
            pass
        """,
    )
    with pytest.raises(PluginError, match="separate MetaData"):
        run_smoke_load(root)


def test_validate_reports_boundary_violations(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("sneaky", plugin_code="import scripts.seed\n")
    completed = _cli("validate", plugins_dir=plugins_dir)
    assert completed.returncode == 1
    assert "imports 'scripts.seed'" in completed.stdout


def test_apply_with_an_unknown_key_fails_before_touching_the_database(plugins_dir: Path) -> None:
    completed = _cli("apply", "--key", "nope", plugins_dir=plugins_dir)
    assert completed.returncode == 1
    assert "No plugin found with key(s): nope" in completed.stderr
