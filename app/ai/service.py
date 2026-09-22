from typing import Any

from sqlalchemy.orm import Session

from app.ai.client import AIClient, get_ai_client
from app.ai.tools.base import ToolContext
from app.ai.tools.post_tools import (
    GetPostCommentsTool,
    GetPostTagsTool,
    GetPostTool,
    GetUserPostsTool,
    SearchPostsTool,
)
from app.ai.tools.registry import AIToolRegistry
from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.models.user import User
from app.repositories.setting_repository import SettingRepository
from app.schemas.ai import AIAskResponse, PostReferenceRead
from app.services.activity_log_service import ActivityLogService

_BASE_INSTRUCTIONS = (
    "You are the Native Life assistant. Use the available tools to look up posts, "
    "comments, and tags before answering questions about app content. "
    "Never invent post data you have not retrieved through a tool. "
    "When you reference a specific post, mention that it's from the Native Life app "
    "and credit the author by name in your answer. The app separately shows the "
    "post's image and a link to it, so don't include raw ids or URLs in your text. "
    "Keep answers concise — tool results are already trimmed for brevity. "
    "Each tool call is slow, so minimize round trips: make one search_posts or "
    "get_user_posts call and answer from its results — they already include title, "
    "summary, author, image, and tags, so only call get_post if you need more of a "
    "specific post's content than the summary gives you. For search_posts, prefer "
    "the free-text 'query' argument with natural keywords over guessing exact tag "
    "names — it matches loosely and usually succeeds on the first try, so you "
    "should rarely need to retry a search."
)

_POST_REFERENCE_TOOLS = {"get_post"}
_POST_LIST_TOOLS = {"search_posts", "get_user_posts"}

AI_ALLOWED_LANGUAGES_SETTING_KEY = "ai_allowed_languages"
_ALL_LANGUAGES_VALUE = "all"


def _parse_allowed_languages(raw_value: str | None) -> list[str]:
    if not raw_value or raw_value.strip().lower() == _ALL_LANGUAGES_VALUE:
        return []
    return [language.strip() for language in raw_value.split(",") if language.strip()]


def _language_instruction(allowed_languages: list[str]) -> str:
    if not allowed_languages:
        return "Respond in the same language the user's prompt is written in."
    names = ", ".join(allowed_languages)
    return (
        f"Only respond in one of these languages: {names}. If the user's prompt is "
        f"written in one of them, reply in that same language; otherwise, reply in "
        f"{allowed_languages[0]}."
    )


def build_default_registry() -> AIToolRegistry:
    return AIToolRegistry(
        [
            GetPostTool(),
            SearchPostsTool(),
            GetPostCommentsTool(),
            GetPostTagsTool(),
            GetUserPostsTool(),
        ]
    )


def _extract_post_references(tool_name: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    if tool_name in _POST_REFERENCE_TOOLS:
        return [result]
    if tool_name in _POST_LIST_TOOLS:
        items = result.get("items", [])
        return items if isinstance(items, list) else []
    return []


class AIService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        registry: AIToolRegistry | None = None,
        client: AIClient | None = None,
    ) -> None:
        self._db = db
        self._registry = registry or build_default_registry()
        self._client = client or get_ai_client()
        self._activity_logs = ActivityLogService(db)

    def _build_instructions(self) -> str:
        setting = SettingRepository(self._db).get_by_key(AI_ALLOWED_LANGUAGES_SETTING_KEY)
        allowed_languages = _parse_allowed_languages(setting.value if setting else None)
        return f"{_BASE_INSTRUCTIONS} {_language_instruction(allowed_languages)}"

    def ask(self, prompt: str, actor: User) -> AIAskResponse:
        context = ToolContext(db=self._db, actor=actor)
        referenced_posts: dict[str, dict[str, Any]] = {}

        def handle_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            result = self._registry.execute(name, arguments, context)
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.AI_TOOL_CALLED,
                entity_type="ai_tool",
                metadata={"tool": name},
            )
            for reference in _extract_post_references(name, result):
                post_id = reference.get("post_id")
                if post_id is not None:
                    referenced_posts[post_id] = reference
            return result

        answer = self._client.run(
            instructions=self._build_instructions(),
            input_text=prompt,
            tool_schemas=self._registry.schemas(),
            handle_tool_call=handle_tool_call,
        )
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.AI_RESPONSE_GENERATED,
            entity_type="ai_response",
            metadata={"prompt_length": len(prompt)},
        )
        return AIAskResponse(
            answer=answer,
            posts=[PostReferenceRead.model_validate(item) for item in referenced_posts.values()],
        )
