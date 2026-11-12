from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.ai.tools.base import AITool, ToolContext
from app.ai.tools.draft_tools import (
    CreateDraftResult,
    DiscardDraftTool,
    NoArgs,
    SaveDraftDetailsTool,
)
from app.core.exceptions import AppError, AuthorizationError
from app.core.messages import AIMessages
from app.core.permissions import PermissionName
from app.models.ai_draft import AIDraftKind
from app.models.user import User
from app.schemas.ai_deal_draft import DealDraftDetails
from app.schemas.ai_draft import AICreatedEntityRead
from app.schemas.pagination import PaginationParams
from app.services.ai_deal_creation_service import AIDealCreationService
from app.services.authorization_service import has_permission
from app.services.category_service import CategoryService

DEALS_ROOT_CATEGORY_SLUG = "deals"
DEAL_CATEGORY_MAX_RESULTS = 50


def can_create_deals(actor: User) -> bool:
    return has_permission(actor, PermissionName.DEAL_CREATE)


def _ensure_can_create_deals(actor: User) -> None:
    if not can_create_deals(actor):
        raise AuthorizationError(AIMessages.DEAL_CREATE_FORBIDDEN)


class DealCategoryReferenceRead(BaseModel):
    id: UUID
    name: str


class ListDealCategoriesResult(BaseModel):
    categories: list[DealCategoryReferenceRead]


class ListDealCategoriesTool(AITool[NoArgs]):
    name = "list_deal_categories"
    description = (
        "List the real categories a Native Life deal can be filed under, with id and name. "
        "Use an id from this list as category_id in save_deal_details; never guess one."
    )
    args_model = NoArgs

    def execute(self, context: ToolContext, arguments: NoArgs) -> ListDealCategoriesResult:
        _ensure_can_create_deals(context.actor)
        categories, _ = CategoryService(context.db).list_by_parent(
            None,
            PaginationParams(page=1, page_size=DEAL_CATEGORY_MAX_RESULTS),
            context.actor,
            parent_slug=DEALS_ROOT_CATEGORY_SLUG,
        )
        return ListDealCategoriesResult(
            categories=[
                DealCategoryReferenceRead(id=category.id, name=category.name)
                for category in categories
            ]
        )


class SaveDealDetailsTool(SaveDraftDetailsTool[DealDraftDetails]):
    name = "save_deal_details"
    description = (
        "Save the deal details the user has given so far while creating a deal. Send only "
        "the fields learned in the latest message; earlier fields are kept. Sending items "
        "replaces the whole item list, so include every item. Dates are ISO 8601 local "
        "times, for example 2026-11-12T18:00:00. Returns everything saved and the list of "
        "fields still missing. Nothing is created yet."
    )
    args_model = DealDraftDetails
    kind = AIDraftKind.DEAL

    def ensure_allowed(self, actor: User) -> None:
        _ensure_can_create_deals(actor)


def _validation_problems(error: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors()
    ]


class CreateDealDraftTool(AITool[NoArgs]):
    name = "create_deal_draft"
    description = (
        "Turn the saved deal details into a DRAFT deal. Call it only after the user has "
        "confirmed a read-back summary of the saved details. It never publishes: the user "
        "must still add cover images in the app and submit the draft. On success the saved "
        "details are cleared. If problems are returned nothing was created; explain them "
        "and ask the user to correct them."
    )
    args_model = NoArgs

    def execute(self, context: ToolContext, arguments: NoArgs) -> CreateDraftResult:
        _ensure_can_create_deals(context.actor)
        try:
            deal = AIDealCreationService(context.db).complete(context.actor)
        except ValidationError as error:
            return CreateDraftResult(created=False, problems=_validation_problems(error))
        except AppError as error:
            return CreateDraftResult(created=False, problems=[error.message])
        return CreateDraftResult(
            created=True,
            entity=AICreatedEntityRead(
                kind=AIDraftKind.DEAL, id=deal.id, title=deal.name, status=deal.status
            ),
        )


class DiscardDealDetailsTool(DiscardDraftTool):
    name = "discard_deal_details"
    description = (
        "Delete the saved deal details when the user wants to cancel or start the deal "
        "over. No deal is created."
    )
    kind = AIDraftKind.DEAL
    details_model = DealDraftDetails

    def ensure_allowed(self, actor: User) -> None:
        _ensure_can_create_deals(actor)
