from pydantic import BaseModel, ConfigDict

from app.ai.tools.base import AITool, ToolContext
from app.schemas.ai import AIPersonalizationContext
from app.services.user_settings_service import UserSettingsService


class GetUserSettingsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetUserSettingsTool(AITool[GetUserSettingsArgs]):
    name = "get_user_settings"
    description = (
        "Retrieve the authenticated user's AI personalization preferences — preferred "
        "language, response style, and preferred content categories/locations — to help "
        "tailor your answer. Always reflects the current user, never another user. Does "
        "not include notification, privacy, or other account settings."
    )
    args_model = GetUserSettingsArgs

    def execute(
        self, context: ToolContext, arguments: GetUserSettingsArgs
    ) -> AIPersonalizationContext:
        content = UserSettingsService(context.db).get_content(context.actor)
        return AIPersonalizationContext(
            ai_enabled=context.ai_enabled,
            personalization_enabled=context.personalization_enabled,
            preferred_language=context.preferred_language,
            response_style=context.response_style,
            preferred_category_names=[tag.name for tag in content.preferred_categories],
            preferred_district_names=[
                district.name for district in content.preferred_locations
            ],
        )
