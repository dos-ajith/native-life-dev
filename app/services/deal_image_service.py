from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import DealMessages
from app.core.storage import delete_private_document, save_deal_image
from app.models.deal import Deal
from app.models.deal_image import DealImage
from app.models.user import User
from app.repositories.deal_repository import DealRepository
from app.schemas.deal import MAX_DEAL_IMAGES, DealRead
from app.services.activity_log_service import ActivityLogService
from app.services.deal_access_policy import DealAccessPolicy, get_deal
from app.services.deal_expiry_service import DealExpiryService
from app.services.deal_service import DealService

ENTITY_TYPE = "deal_image"


def _find_image(deal: Deal, image_id: UUID) -> DealImage:
    image = next((image for image in deal.images if image.id == image_id), None)
    if image is None:
        raise NotFoundError(DealMessages.IMAGE_NOT_FOUND)
    return image


class DealImageService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._deals = DealRepository(db)
        self._deal_service = DealService(db)
        self._access = DealAccessPolicy(db)
        self._expiry = DealExpiryService(db)
        self._activity_logs = ActivityLogService(db)

    def add(
        self,
        deal_id: UUID,
        file: UploadFile,
        is_thumbnail: bool,
        private_upload_dir: str,
        actor: User,
    ) -> DealRead:
        deal = self._deal_service.get_owned_draft(deal_id, actor)
        if len(deal.images) >= MAX_DEAL_IMAGES:
            raise BusinessRuleError(DealMessages.TOO_MANY_IMAGES.format(limit=MAX_DEAL_IMAGES))
        storage_path, content_type, size_bytes = save_deal_image(file, private_upload_dir)
        current_thumbnail = next((image for image in deal.images if image.is_thumbnail), None)
        becomes_thumbnail = is_thumbnail or current_thumbnail is None
        try:
            if becomes_thumbnail and current_thumbnail is not None:
                current_thumbnail.is_thumbnail = False
                self._db.flush()
            image = DealImage(
                storage_path=storage_path,
                content_type=content_type,
                file_size_bytes=size_bytes,
                is_thumbnail=becomes_thumbnail,
                sort_order=max((image.sort_order for image in deal.images), default=-1) + 1,
            )
            deal.images.append(image)
            saved = self._deals.save(deal)
        except Exception:
            self._db.rollback()
            delete_private_document(storage_path)
            raise
        self._log(actor, ActivityAction.DEAL_IMAGE_ADDED, image.id, deal.id)
        return DealRead.from_deal(saved, actor)

    def remove(self, deal_id: UUID, image_id: UUID, actor: User) -> DealRead:
        deal = self._deal_service.get_owned_draft(deal_id, actor)
        image = _find_image(deal, image_id)
        storage_path = image.storage_path
        for item in deal.items:
            if item.image_id == image_id:
                item.image_id = None
        deal.images.remove(image)
        self._db.flush()
        if image.is_thumbnail and deal.images:
            deal.images[0].is_thumbnail = True
        saved = self._deals.save(deal)
        delete_private_document(storage_path)
        self._log(actor, ActivityAction.DEAL_IMAGE_REMOVED, image_id, deal.id)
        return DealRead.from_deal(saved, actor)

    def set_thumbnail(self, deal_id: UUID, image_id: UUID, actor: User) -> DealRead:
        deal = self._deal_service.get_owned_draft(deal_id, actor)
        image = _find_image(deal, image_id)
        for other in deal.images:
            if other.is_thumbnail and other.id != image_id:
                other.is_thumbnail = False
        self._db.flush()
        image.is_thumbnail = True
        saved = self._deals.save(deal)
        self._log(actor, ActivityAction.DEAL_THUMBNAIL_SET, image_id, deal.id)
        return DealRead.from_deal(saved, actor)

    def get_viewable(self, deal_id: UUID, image_id: UUID, viewer: User) -> DealImage:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_view(deal, viewer)
        return _find_image(deal, image_id)

    def _log(self, actor: User, action: str, image_id: UUID, deal_id: UUID) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=image_id,
            metadata={"deal_id": str(deal_id)},
        )
