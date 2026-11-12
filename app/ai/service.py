from typing import Any

from sqlalchemy.orm import Session

from app.ai.client import AIClient, get_ai_client
from app.ai.draft_flows import DRAFT_FLOWS, render_draft_progress
from app.ai.policy import NATIVE_LIFE_SYSTEM_PROMPT
from app.ai.retrieval import NativeLifeRetriever, render_retrieval_context
from app.ai.search_intent import extract_search_intent
from app.ai.tools.base import AITool, ToolContext
from app.ai.tools.business_tools import SearchBusinessCategoriesTool, SearchBusinessesTool
from app.ai.tools.event_tools import GetEventTool, SearchEventsTool
from app.ai.tools.geography_tools import GetNearbyContentTool, SearchLocationsTool
from app.ai.tools.post_tools import (
    GetPostCommentsTool,
    GetPostTagsTool,
    GetPostTool,
    GetUserPostsTool,
    SearchPostsTool,
)
from app.ai.tools.registry import AIToolRegistry
from app.ai.tools.tag_tools import SearchTagsTool
from app.ai.tools.user_settings_tools import GetUserSettingsTool
from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import BusinessRuleError
from app.core.messages import AIMessages
from app.core.timezone import app_now
from app.models.plugin import PluginStatus
from app.models.user import User
from app.models.user_settings_enums import AIResponseStyle
from app.plugins.registry import PluginRegistry
from app.repositories.plugin_repository import PluginRepository
from app.repositories.setting_repository import SettingRepository
from app.schemas.ai import AIAskResponse, PostReferenceRead, UserLocation
from app.schemas.ai_draft import AICreatedEntityRead
from app.services.activity_log_service import ActivityLogService
from app.services.user_settings_service import UserSettingsService

_RESPONSE_STYLE_INSTRUCTIONS: dict[AIResponseStyle, str] = {
    AIResponseStyle.CONCISE: (
        "Keep your final answer brief — a sentence or two. Tool results are already "
        "trimmed for brevity, so don't restate them at length."
    ),
    AIResponseStyle.BALANCED: (
        "Keep your final answer to a short paragraph — enough context to be useful "
        "without restating everything a tool returned."
    ),
    AIResponseStyle.DETAILED: (
        "Give a thorough final answer — include relevant context and detail from the "
        "tool results rather than compressing them down to the bare minimum."
    ),
}

_POST_REFERENCE_TOOLS = {"get_post"}
_POST_LIST_TOOLS = {"search_posts", "get_user_posts"}

AI_ALLOWED_LANGUAGES_SETTING_KEY = "ai_allowed_languages"
_ALL_LANGUAGES_VALUE = "all"


def _parse_allowed_languages(raw_value: str | None) -> list[str]:
    if not raw_value or raw_value.strip().lower() == _ALL_LANGUAGES_VALUE:
        return []
    return [language.strip() for language in raw_value.split(",") if language.strip()]


def _resolve_effective_language(preferred_language: str, allowed_languages: list[str]) -> str:
    if not allowed_languages:
        return preferred_language
    normalized_allowed = {language.lower() for language in allowed_languages}
    if preferred_language.lower() in normalized_allowed:
        return preferred_language
    return allowed_languages[0]


def _response_style_instruction(response_style: AIResponseStyle) -> str:
    return _RESPONSE_STYLE_INSTRUCTIONS[response_style]


def _language_instruction(effective_language: str, allowed_languages: list[str]) -> str:
    preference = (
        f"The user's preferred language code is '{effective_language}'. Respond in "
        f"that language unless the user's prompt is clearly written in a different "
        f"language you're allowed to use, in which case respond in that language "
        f"instead."
    )
    if not allowed_languages:
        return preference
    names = ", ".join(allowed_languages)
    return f"Only respond in one of these languages: {names}. {preference}"


def build_default_registry() -> AIToolRegistry:
    return AIToolRegistry(
        [
            GetPostTool(),
            SearchPostsTool(),
            GetPostCommentsTool(),
            GetPostTagsTool(),
            GetUserPostsTool(),
            SearchTagsTool(),
            SearchLocationsTool(),
            GetNearbyContentTool(),
            SearchBusinessCategoriesTool(),
            SearchBusinessesTool(),
            SearchEventsTool(),
            GetEventTool(),
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
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        self._db = db
        self._plugin_registry = plugin_registry or PluginRegistry()
        self._registry = registry or build_default_registry()
        self._client = client or get_ai_client()
        self._activity_logs = ActivityLogService(db)
        self._user_settings = UserSettingsService(db)

    def _plugin_tools(self) -> list[AITool[Any]]:
        serving = {
            plugin.key: plugin.version
            for plugin in PluginRepository(self._db).list_all()
            if plugin.status == PluginStatus.ENABLED
        }
        return [
            tool
            for plugin in self._plugin_registry.plugins
            if serving.get(plugin.key) == str(plugin.manifest.version)
            for tool in plugin.ai_tools
        ]

    def _build_instructions(self, preferred_language: str, response_style: AIResponseStyle) -> str:
        setting = SettingRepository(self._db).get_by_key(AI_ALLOWED_LANGUAGES_SETTING_KEY)
        allowed_languages = _parse_allowed_languages(setting.value if setting else None)
        effective_language = _resolve_effective_language(preferred_language, allowed_languages)
        return (
            f"{NATIVE_LIFE_SYSTEM_PROMPT} {_response_style_instruction(response_style)} "
            f"{_language_instruction(effective_language, allowed_languages)} "
            f"Current date and time: {app_now().isoformat(timespec='minutes')}."
        )

    def ask(
        self, prompt: str, actor: User, user_location: UserLocation | None = None
    ) -> AIAskResponse:
        ai_settings = self._user_settings.get_ai(actor)
        if not ai_settings.ai_enabled:
            raise BusinessRuleError(AIMessages.AI_DISABLED_BY_USER)

        registry = self._registry.with_tools(self._plugin_tools())
        if ai_settings.personalization_enabled:
            registry = registry.with_tool(GetUserSettingsTool())
        draft_flows = [flow for flow in DRAFT_FLOWS if flow.is_available(actor)]
        draft_progress_blocks: list[str] = []
        for flow in draft_flows:
            registry = registry.with_tools(flow.tools())
            progress = flow.progress(self._db, actor)
            if progress is not None:
                draft_progress_blocks.append(render_draft_progress(flow.kind, progress))
        create_tool_names = {flow.create_tool_name for flow in draft_flows}

        context = ToolContext(
            db=self._db,
            actor=actor,
            ai_enabled=ai_settings.ai_enabled,
            personalization_enabled=ai_settings.personalization_enabled,
            preferred_language=ai_settings.preferred_language,
            response_style=ai_settings.response_style,
        )
        referenced_posts: dict[str, dict[str, Any]] = {}
        created_entity: AICreatedEntityRead | None = None
        input_text = prompt

        intent = extract_search_intent(self._client, prompt)
        if intent is not None and intent.is_searchable:
            retrieved = NativeLifeRetriever(self._db, actor, user_location).retrieve(intent)
            input_text = render_retrieval_context(prompt, intent, retrieved, user_location)
            for post in retrieved.posts:
                referenced_posts[str(post.post_id)] = post.model_dump(mode="json")

        if draft_progress_blocks:
            input_text = "\n\n".join([input_text, *draft_progress_blocks])

        def handle_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            nonlocal created_entity
            result = registry.execute(name, arguments, context)
            if name in create_tool_names and result.get("created"):
                created_entity = AICreatedEntityRead.model_validate(result["entity"])
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
            instructions=self._build_instructions(
                ai_settings.preferred_language, ai_settings.response_style
            ),
            input_text=input_text,
            tool_schemas=registry.schemas(),
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
            created=created_entity,
        )
