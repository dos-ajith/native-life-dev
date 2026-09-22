import json
from collections.abc import Callable
from functools import lru_cache
from typing import Any, Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from app.ai.exceptions import AIProviderError, AIProviderTimeoutError, AIResponseError
from app.core.config import Settings, get_settings
from app.core.messages import AIMessages

ToolCallHandler = Callable[[str, dict[str, Any]], dict[str, Any]]


def _call_with_provider_error_handling(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except APITimeoutError as exc:
        raise AIProviderTimeoutError(AIMessages.PROVIDER_TIMEOUT) from exc
    except (APIConnectionError, APIStatusError) as exc:
        raise AIProviderError(AIMessages.PROVIDER_UNAVAILABLE) from exc


class _AIBackend(Protocol):
    def run(
        self,
        instructions: str,
        input_text: str,
        tool_schemas: list[dict[str, Any]],
        handle_tool_call: ToolCallHandler,
    ) -> str: ...


class _ResponsesBackend:
    """OpenAI's Responses API — used for the "openai" provider."""

    def __init__(
        self, client: OpenAI, model: str, max_output_tokens: int, max_tool_iterations: int
    ) -> None:
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._max_tool_iterations = max_tool_iterations

    def _create_response(self, **kwargs: Any) -> Any:
        return _call_with_provider_error_handling(
            lambda: self._client.responses.create(
                model=self._model, max_output_tokens=self._max_output_tokens, **kwargs
            )
        )

    def run(
        self,
        instructions: str,
        input_text: str,
        tool_schemas: list[dict[str, Any]],
        handle_tool_call: ToolCallHandler,
    ) -> str:
        response = self._create_response(
            instructions=instructions, input=input_text, tools=tool_schemas
        )

        for _ in range(self._max_tool_iterations):
            function_calls = [item for item in response.output if item.type == "function_call"]
            if not function_calls:
                return self._extract_text(response)

            outputs = []
            for call in function_calls:
                try:
                    arguments = json.loads(call.arguments)
                except json.JSONDecodeError as exc:
                    raise AIResponseError(AIMessages.MALFORMED_RESPONSE) from exc
                result = handle_tool_call(call.name, arguments)
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result),
                    }
                )

            response = self._create_response(
                previous_response_id=response.id, input=outputs, tools=tool_schemas
            )

        raise AIResponseError(AIMessages.TOOL_ITERATION_LIMIT_EXCEEDED)

    def _extract_text(self, response: Any) -> str:
        text = getattr(response, "output_text", None)
        if not isinstance(text, str) or not text:
            raise AIResponseError(AIMessages.MALFORMED_RESPONSE)
        return text


class _ChatCompletionsBackend:
    """OpenAI-compatible Chat Completions API — used for the "groq" provider,
    since Groq does not implement the Responses API."""

    def __init__(
        self, client: OpenAI, model: str, max_output_tokens: int, max_tool_iterations: int
    ) -> None:
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._max_tool_iterations = max_tool_iterations

    def _to_chat_tools(self, tool_schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema["parameters"],
                },
            }
            for schema in tool_schemas
        ]

    def _create_completion(self, **kwargs: Any) -> Any:
        return _call_with_provider_error_handling(
            lambda: self._client.chat.completions.create(
                model=self._model, max_tokens=self._max_output_tokens, **kwargs
            )
        )

    def run(
        self,
        instructions: str,
        input_text: str,
        tool_schemas: list[dict[str, Any]],
        handle_tool_call: ToolCallHandler,
    ) -> str:
        chat_tools = self._to_chat_tools(tool_schemas)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": input_text},
        ]

        for _ in range(self._max_tool_iterations):
            response = self._create_completion(messages=messages, tools=chat_tools)
            message = response.choices[0].message
            tool_calls = message.tool_calls or []
            if not tool_calls:
                return self._extract_text(message)

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                try:
                    arguments = json.loads(call.function.arguments)
                except json.JSONDecodeError as exc:
                    raise AIResponseError(AIMessages.MALFORMED_RESPONSE) from exc
                result = handle_tool_call(call.function.name, arguments)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
                )

        raise AIResponseError(AIMessages.TOOL_ITERATION_LIMIT_EXCEEDED)

    def _extract_text(self, message: Any) -> str:
        text = getattr(message, "content", None)
        if not isinstance(text, str) or not text:
            raise AIResponseError(AIMessages.MALFORMED_RESPONSE)
        return text


def _build_backend(settings: Settings) -> _AIBackend:
    if settings.ai_provider == "groq":
        if not settings.groq_api_key:
            raise AIProviderError(AIMessages.PROVIDER_UNAVAILABLE)
        client = OpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            timeout=settings.ai_request_timeout_seconds,
        )
        return _ChatCompletionsBackend(
            client,
            settings.ai_model,
            settings.ai_max_output_tokens,
            settings.ai_max_tool_iterations,
        )

    if not settings.openai_api_key:
        raise AIProviderError(AIMessages.PROVIDER_UNAVAILABLE)
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_request_timeout_seconds)
    return _ResponsesBackend(
        client, settings.ai_model, settings.ai_max_output_tokens, settings.ai_max_tool_iterations
    )


class AIClient:
    def __init__(self, settings: Settings) -> None:
        self._backend = _build_backend(settings)

    def run(
        self,
        instructions: str,
        input_text: str,
        tool_schemas: list[dict[str, Any]],
        handle_tool_call: ToolCallHandler,
    ) -> str:
        return self._backend.run(instructions, input_text, tool_schemas, handle_tool_call)


@lru_cache
def get_ai_client() -> AIClient:
    """Reuses one SDK client (and its underlying HTTP connection pool) across
    requests instead of paying a fresh TCP/TLS handshake on every /ai/ask call."""
    return AIClient(get_settings())
