from pathlib import Path
from typing import Any, cast

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.plugins.bootstrap import load_plugin_registry
from app.plugins.registry import PluginLoadState


class MissingPluginTableSession:
    def __init__(self) -> None:
        self.rolled_back = False

    def scalars(self, *_args: Any, **_kwargs: Any) -> Any:
        raise ProgrammingError("SELECT plugins", {}, Exception('relation "plugins" does not exist'))

    def rollback(self) -> None:
        self.rolled_back = True


def test_unreadable_registry_lets_the_core_start_without_plugins(tmp_path: Path) -> None:
    session = MissingPluginTableSession()
    settings = get_settings().model_copy(update={"plugins_dir": str(tmp_path)})
    registry = load_plugin_registry(cast(Session, session), settings)
    assert registry.plugins == ()
    assert [outcome.state for outcome in registry.outcomes] == [PluginLoadState.FAILED]
    assert session.rolled_back
