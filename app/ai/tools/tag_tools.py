from pydantic import BaseModel, ConfigDict

from app.ai.tools.base import AITool, SearchQuery, ToolContext
from app.services.tag_service import TagService

_MAX_RESULTS = 10


class SearchTagsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: SearchQuery


class TagReferenceRead(BaseModel):
    name: str


class SearchTagsResult(BaseModel):
    items: list[TagReferenceRead]


class SearchTagsTool(AITool[SearchTagsArgs]):
    name = "search_tags"
    description = (
        "Search existing Native Life tags/categories by free-text name (e.g. 'food'). "
        "Returns up to 10 matching tag names — use the exact names from the result as "
        "the 'tags' argument to search_posts."
    )
    args_model = SearchTagsArgs

    def execute(self, context: ToolContext, arguments: SearchTagsArgs) -> SearchTagsResult:
        tags = TagService(context.db).search(arguments.query, _MAX_RESULTS)
        return SearchTagsResult(items=[TagReferenceRead(name=tag.name) for tag in tags])
