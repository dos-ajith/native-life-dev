from datetime import timedelta

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.models.ai_draft import AIDraftKind
from app.models.user import User
from app.repositories.ai_draft_repository import AIDraftRepository
from app.schemas.ai_draft import AIDraftDetails, AIDraftProgressRead
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "ai_draft"
AI_DRAFT_TTL = timedelta(hours=24)


class AIDraftService[DetailsT: AIDraftDetails]:
    def __init__(self, db: Session, kind: AIDraftKind, details_model: type[DetailsT]) -> None:
        self._kind = kind
        self._details_model = details_model
        self._drafts = AIDraftRepository(db)
        self._activity_logs = ActivityLogService(db)

    def get(self, actor: User) -> DetailsT | None:
        self._drafts.delete_stale(actor.id, self._kind, AI_DRAFT_TTL)
        draft = self._drafts.get(actor.id, self._kind)
        if draft is None:
            return None
        return self._details_model.model_validate(draft.details)

    def progress(self, actor: User) -> AIDraftProgressRead[DetailsT] | None:
        details = self.get(actor)
        if details is None:
            return None
        return AIDraftProgressRead[DetailsT](details=details, missing=details.missing_fields())

    def save(self, actor: User, changes: DetailsT) -> AIDraftProgressRead[DetailsT]:
        current = self.get(actor)
        saved_fields = _stored_form(changes)
        stored_fields = _stored_form(current) if current is not None else {}
        details = self._details_model.model_validate({**stored_fields, **saved_fields})
        self._drafts.upsert(actor.id, self._kind, _stored_form(details))
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.AI_DRAFT_SAVED,
            entity_type=ENTITY_TYPE,
            metadata={"kind": self._kind, "fields": sorted(saved_fields)},
        )
        return AIDraftProgressRead[DetailsT](details=details, missing=details.missing_fields())

    def discard(self, actor: User) -> bool:
        discarded = self._drafts.delete(actor.id, self._kind)
        if discarded:
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.AI_DRAFT_DISCARDED,
                entity_type=ENTITY_TYPE,
                metadata={"kind": self._kind},
            )
        return discarded

    def clear(self, actor: User) -> None:
        self._drafts.delete(actor.id, self._kind)


def _stored_form(details: BaseModel) -> dict[str, object]:
    return details.model_dump(mode="json", exclude_none=True)
