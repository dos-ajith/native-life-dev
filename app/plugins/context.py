from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter
from sqlalchemy.orm import DeclarativeBase

from app.ai.tools.base import AITool
from app.core.messages import PluginMessages
from app.plugins.deal_commerce import DealCommerceProvider
from app.plugins.errors import PluginError
from app.plugins.manifest import PluginManifest


@dataclass(frozen=True)
class PluginContribution:
    routers: tuple[APIRouter, ...]
    model_bases: tuple[type[DeclarativeBase], ...]
    ai_tools: tuple[AITool[Any], ...] = ()
    deal_commerce: DealCommerceProvider | None = None


class PluginContext:
    def __init__(self, manifest: PluginManifest) -> None:
        self._manifest = manifest
        self._routers: list[APIRouter] = []
        self._model_bases: list[type[DeclarativeBase]] = []
        self._ai_tools: list[AITool[Any]] = []
        self._deal_commerce: DealCommerceProvider | None = None
        self._closed = False

    @property
    def key(self) -> str:
        return self._manifest.key

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def include_router(self, router: APIRouter) -> None:
        self._ensure_open()
        self._routers.append(router)

    def register_models(self, base: type[DeclarativeBase]) -> None:
        self._ensure_open()
        self._model_bases.append(base)

    def register_ai_tool(self, tool: AITool[Any]) -> None:
        self._ensure_open()
        prefix = f"{self.key}_"
        if not tool.name.startswith(prefix) or tool.name == prefix:
            raise PluginError(
                PluginMessages.AI_TOOL_NAME_INVALID.format(name=tool.name, prefix=prefix)
            )
        if any(existing.name == tool.name for existing in self._ai_tools):
            raise PluginError(PluginMessages.AI_TOOL_DUPLICATE.format(name=tool.name))
        self._ai_tools.append(tool)

    def register_deal_commerce(self, provider: DealCommerceProvider) -> None:
        self._ensure_open()
        if self._deal_commerce is not None:
            raise PluginError(PluginMessages.DEAL_COMMERCE_DUPLICATE)
        self._deal_commerce = provider

    def close(self) -> PluginContribution:
        self._closed = True
        return PluginContribution(
            routers=tuple(self._routers),
            model_bases=tuple(self._model_bases),
            ai_tools=tuple(self._ai_tools),
            deal_commerce=self._deal_commerce,
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise PluginError(PluginMessages.CONTEXT_CLOSED)
