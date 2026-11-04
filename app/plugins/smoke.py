import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI

from app.core.messages import PluginMessages
from app.plugins.discovery import load_candidate
from app.plugins.errors import PluginError
from app.plugins.loader import load_plugin
from app.plugins.mounting import mount_plugin
from app.plugins.versioning import CORE_API_VERSION

SMOKE_TIMEOUT_SECONDS = 60
SMOKE_ERROR_MAX_LENGTH = 500
CLI_MODULE = "app.plugins.cli"
SMOKE_COMMAND = "smoke"


def smoke_load_in_process(root: Path) -> None:
    candidate = load_candidate(root)
    if not candidate.manifest.core_api.allows(CORE_API_VERSION):
        raise PluginError(
            PluginMessages.INCOMPATIBLE_CORE_API.format(
                required=candidate.manifest.compatibility.core_api, provided=CORE_API_VERSION
            )
        )
    loaded = load_plugin(candidate)
    app = FastAPI()
    mount_plugin(app, loaded, api_prefix="")
    app.openapi()


def _last_line(output: str) -> str:
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return (lines[-1] if lines else "")[:SMOKE_ERROR_MAX_LENGTH]


def run_smoke_load(root: Path) -> None:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", CLI_MODULE, SMOKE_COMMAND, str(root)],
            capture_output=True,
            text=True,
            timeout=SMOKE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PluginError(
            PluginMessages.SMOKE_LOAD_TIMED_OUT.format(seconds=SMOKE_TIMEOUT_SECONDS)
        ) from exc
    if completed.returncode != 0:
        raise PluginError(
            PluginMessages.SMOKE_LOAD_FAILED.format(error=_last_line(completed.stderr))
        )
