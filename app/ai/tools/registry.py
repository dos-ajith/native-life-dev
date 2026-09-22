from typing import Any

from pydantic import ValidationError

from app.ai.exceptions import (
    AIToolExecutionError,
    InvalidAIToolArgumentsError,
    UnknownAIToolError,
)
from app.ai.tools.base import AITool, ToolContext
from app.core.exceptions import AppError
from app.core.messages import AIMessages


class AIToolRegistry:
    def __init__(self, tools: list[AITool[Any]]) -> None:
        self._tools: dict[str, AITool[Any]] = {tool.name: tool for tool in tools}

    def with_tool(self, tool: AITool[Any]) -> "AIToolRegistry":
        return AIToolRegistry([*self._tools.values(), tool])

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_model.model_json_schema(),
            }
            for tool in self._tools.values()
        ]

    def execute(
        self, name: str, raw_arguments: dict[str, Any], context: ToolContext
    ) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownAIToolError(AIMessages.UNKNOWN_TOOL.format(name=name))

        try:
            arguments = tool.args_model.model_validate(raw_arguments)
        except ValidationError as exc:
            raise InvalidAIToolArgumentsError(
                AIMessages.INVALID_TOOL_ARGUMENTS.format(name=name)
            ) from exc

        try:
            result = tool.execute(context, arguments)
        except AppError:
            raise
        except Exception as exc:
            raise AIToolExecutionError(AIMessages.TOOL_EXECUTION_FAILED) from exc

        return result.model_dump(mode="json")
