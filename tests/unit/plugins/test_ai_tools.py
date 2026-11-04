from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from app.ai.service import AIService
from app.models.plugin import PluginStatus
from app.plugins.discovery import load_candidate
from app.plugins.errors import PluginError
from app.plugins.loader import LoadedPlugin, load_plugin
from app.plugins.registry import PluginRegistry
from tests.unit.plugins.conftest import PluginWriter

TOOL_CODE = """
from pydantic import BaseModel

from app.plugins.sdk import AITool, PluginContext


class Args(BaseModel):
    pass


class Result(BaseModel):
    ok: bool = True


class Tool(AITool[Args]):
    name = "{tool_name}"
    description = "Test tool"
    args_model = Args

    def execute(self, context, arguments):
        return Result()


def register(ctx: PluginContext) -> None:
    ctx.register_ai_tool(Tool())
{extra}
"""


def code(tool_name: str, extra: str = "") -> str:
    return TOOL_CODE.format(tool_name=tool_name, extra=extra)


def test_a_plugin_contributes_its_prefixed_ai_tool(write_plugin: PluginWriter) -> None:
    root = write_plugin("shop", plugin_code=code("shop_search"))

    loaded = load_plugin(load_candidate(root))

    assert [tool.name for tool in loaded.ai_tools] == ["shop_search"]


@pytest.mark.parametrize("tool_name", ["search", "other_search", "shop_"])
def test_an_ai_tool_must_carry_the_plugin_key_prefix(
    write_plugin: PluginWriter, tool_name: str
) -> None:
    root = write_plugin("shop", plugin_code=code(tool_name))

    with pytest.raises(PluginError):
        load_plugin(load_candidate(root))


def test_the_same_ai_tool_cannot_be_registered_twice(write_plugin: PluginWriter) -> None:
    extra = "    ctx.register_ai_tool(Tool())\n"
    root = write_plugin("shop", plugin_code=code("shop_search", extra))

    with pytest.raises(PluginError):
        load_plugin(load_candidate(root))


class FakeTool:
    name = "shop_search"
    description = "d"
    args_model = BaseModel


def loaded_plugin(key: str, version: str) -> LoadedPlugin:
    return LoadedPlugin(
        manifest=SimpleNamespace(key=key, version=version),  # type: ignore[arg-type]
        root=MagicMock(),
        content_sha256="0",
        routers=(),
        model_bases=(),
        ai_tools=(FakeTool(),),  # type: ignore[arg-type]
    )


def stored(key: str, version: str, status: PluginStatus) -> SimpleNamespace:
    return SimpleNamespace(key=key, version=version, status=status)


def tool_names(stored_plugins: list[SimpleNamespace]) -> list[str]:
    registry = PluginRegistry(plugins=(loaded_plugin("shop", "1.0.0"),))
    service = AIService(MagicMock(), MagicMock(), client=MagicMock(), plugin_registry=registry)
    with patch("app.ai.service.PluginRepository") as repository:
        repository.return_value.list_all.return_value = stored_plugins
        return [tool.name for tool in service._plugin_tools()]


def test_ai_exposes_tools_of_enabled_plugins() -> None:
    assert tool_names([stored("shop", "1.0.0", PluginStatus.ENABLED)]) == ["shop_search"]


@pytest.mark.parametrize(
    "stored_plugin",
    [
        stored("shop", "1.0.0", PluginStatus.DISABLED),
        stored("shop", "1.0.0", PluginStatus.INSTALLED),
        stored("shop", "0.9.0", PluginStatus.ENABLED),
    ],
)
def test_ai_hides_tools_of_plugins_that_are_not_serving(stored_plugin: SimpleNamespace) -> None:
    assert tool_names([stored_plugin]) == []


def test_ai_has_no_plugin_tools_without_any_plugin_stored() -> None:
    assert tool_names([]) == []
