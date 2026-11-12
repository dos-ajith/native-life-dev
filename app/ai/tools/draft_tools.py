from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from app.ai.tools.base import AITool, ToolContext
from app.models.ai_draft import AIDraftKind
from app.models.user import User
from app.schemas.ai_draft import AICreatedEntityRead, AIDraftDetails, AIDraftProgressRead
from app.services.ai_draft_service import AIDraftService


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateDraftResult(BaseModel):
    created: bool
    entity: AICreatedEntityRead | None = None
    problems: list[str] = []


class DiscardDraftResult(BaseModel):
    discarded: bool


class SaveDraftDetailsTool[DetailsT: AIDraftDetails](AITool[DetailsT]):
    kind: ClassVar[AIDraftKind]

    def ensure_allowed(self, actor: User) -> None:
        raise NotImplementedError

    def execute(self, context: ToolContext, arguments: DetailsT) -> AIDraftProgressRead[DetailsT]:
        self.ensure_allowed(context.actor)
        drafts = AIDraftService(context.db, self.kind, self.args_model)
        return drafts.save(context.actor, arguments)


class DiscardDraftTool(AITool[NoArgs]):
    kind: ClassVar[AIDraftKind]
    details_model: ClassVar[type[AIDraftDetails]]
    args_model = NoArgs

    def ensure_allowed(self, actor: User) -> None:
        raise NotImplementedError

    def execute(self, context: ToolContext, arguments: NoArgs) -> DiscardDraftResult:
        self.ensure_allowed(context.actor)
        drafts = AIDraftService(context.db, self.kind, self.details_model)
        return DiscardDraftResult(discarded=drafts.discard(context.actor))
