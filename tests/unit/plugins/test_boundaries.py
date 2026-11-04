from pathlib import Path

import pytest

from app.plugins.boundaries import find_boundary_violations
from tests.unit.plugins.conftest import REFERENCE_PLUGIN_ROOT


def _write(root: Path, name: str, code: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)


def test_reference_plugin_respects_boundaries() -> None:
    assert find_boundary_violations(REFERENCE_PLUGIN_ROOT) == []


def test_sdk_relative_and_third_party_imports_are_allowed(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "plugin.py",
        "import json\n"
        "import app.plugins.sdk\n"
        "from app.plugins import sdk\n"
        "from app.plugins.sdk import PluginContext\n"
        "from fastapi import APIRouter\n"
        "from .routes import router\n",
    )
    assert find_boundary_violations(tmp_path) == []


def test_core_imports_outside_the_sdk_are_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "plugin.py",
        "from app.models.business import Business\n"
        "import app.core.config\n"
        "from app.plugins import loader\n"
        "import app\n",
    )
    violations = find_boundary_violations(tmp_path)
    assert len(violations) == 4
    assert "plugin.py:1 imports 'app.models.business'" in violations[0]


def test_backref_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "models.py",
        "from sqlalchemy.orm import backref, relationship\n"
        "a = relationship('X', backref='items')\n"
        "b = relationship('X', backref=backref('items'))\n",
    )
    violations = find_boundary_violations(tmp_path)
    assert len(violations) == 3
    assert all("backref" in violation for violation in violations)


def test_syntax_errors_are_reported(tmp_path: Path) -> None:
    _write(tmp_path, "broken.py", "def broken(:\n")
    assert "broken.py:1" in find_boundary_violations(tmp_path)[0]


def test_tests_directory_is_excluded(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_x.py", "from app.models.business import Business\n")
    assert find_boundary_violations(tmp_path) == []


def test_repository_local_packages_and_other_plugins_are_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "plugin.py",
        "import scripts.seed\n"
        "from migrations import env\n"
        "from plugins._reference.hello import routes\n"
        "import native_life_plugin_other\n"
        "import tests.conftest\n",
    )
    assert len(find_boundary_violations(tmp_path)) == 5


def test_production_code_cannot_import_the_plugin_tests_package(tmp_path: Path) -> None:
    _write(tmp_path, "plugin.py", "from .tests import helper\nfrom . import tests\n")
    _write(tmp_path, "api/routes.py", "from ..tests.helpers import x\nfrom .tests import y\n")
    _write(tmp_path, "api/__init__.py", "")
    _write(tmp_path, "tests/helper.py", "secret = 1\n")
    violations = find_boundary_violations(tmp_path)
    assert len(violations) == 4
    assert all("tests package" in violation for violation in violations)
    assert any("api/routes.py:2" in violation for violation in violations)


def test_production_code_cannot_import_build_tool_directories(tmp_path: Path) -> None:
    _write(tmp_path, "plugin.py", "from .node_modules import shim\nfrom . import node_modules\n")
    _write(tmp_path, "frontend/__init__.py", "from .node_modules.pkg import x\n")
    _write(tmp_path, "frontend/node_modules/pkg/evil.py", "import app.core.config\n")
    _write(tmp_path, ".venv/lib/evil.py", "import app.core.config\n")
    violations = find_boundary_violations(tmp_path)
    assert len(violations) == 3
    assert all("'node_modules'" in violation for violation in violations)


@pytest.mark.parametrize(
    "source",
    [
        "def hijack(request):\n    request.app.dependency_overrides[object] = object\n",
        "def hijack(app):\n    overrides = app.dependency_overrides\n",
        "def hijack(app):\n    getattr(app, 'dependency_overrides').clear()\n",
        "def hijack(app):\n    setattr(app.router, 'dependency_overrides_provider', None)\n",
        "def hijack(app):\n    vars(app)['dependency_overrides'] = {}\n",
        "def hijack(app):\n    provider = app.router.dependency_overrides_provider\n",
        "from fastapi import FastAPI as dependency_overrides\n",
    ],
)
def test_dependency_overrides_are_rejected(tmp_path: Path, source: str) -> None:
    _write(tmp_path, "plugin.py", source)
    violations = find_boundary_violations(tmp_path)
    assert violations
    assert all("dependency_overrides" in violation for violation in violations)


def test_unrelated_dependencies_are_not_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "plugin.py",
        "from fastapi import Depends\n\noverride_count = 0\ndependencies = [Depends(print)]\n",
    )
    assert find_boundary_violations(tmp_path) == []
