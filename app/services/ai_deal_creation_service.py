from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError
from app.core.messages import AIMessages
from app.models.ai_draft import AIDraftKind
from app.models.user import User
from app.schemas.ai_deal_draft import DealDraftDetails
from app.schemas.deal import DealCreate, DealRead
from app.services.ai_draft_service import AIDraftService
from app.services.deal_service import DealService


def deal_drafts(db: Session) -> AIDraftService[DealDraftDetails]:
    return AIDraftService(db, AIDraftKind.DEAL, DealDraftDetails)


class AIDealCreationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._drafts = deal_drafts(db)

    def complete(self, actor: User) -> DealRead:
        details = self._drafts.get(actor)
        if details is None:
            raise BusinessRuleError(AIMessages.DRAFT_EMPTY)
        payload = DealCreate.model_validate(details.model_dump(exclude_none=True))
        deal = DealService(self._db).create(payload, [], get_settings().private_upload_dir, actor)
        self._drafts.clear(actor)
        return deal
