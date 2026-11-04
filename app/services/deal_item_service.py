from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import DealMessages
from app.models.deal import Deal
from app.models.deal_item import DealItem
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.deal_repository import DealRepository
from app.schemas.deal import (
    MAX_DEAL_ITEMS,
    DealItemCreate,
    DealItemUpdate,
    DealRead,
    ensure_price_order,
)
from app.services.activity_log_service import ActivityLogService
from app.services.deal_product_item_service import DealProductItemService
from app.services.deal_service import DealService

ENTITY_TYPE = "deal_item"
CLEARABLE_FIELDS = frozenset(
    {"description", "quantity", "original_price", "deal_price", "image_id"}
)
PRODUCT_LOCKED_FIELDS = frozenset({"name", "unit", "original_price"})


def _ensure_image_in_deal(deal: Deal, image_id: UUID | None) -> None:
    if image_id is not None and all(image.id != image_id for image in deal.images):
        raise NotFoundError(DealMessages.IMAGE_NOT_FOUND)


def _find_item(deal: Deal, item_id: UUID) -> DealItem:
    item = next((item for item in deal.items if item.id == item_id), None)
    if item is None:
        raise NotFoundError(DealMessages.ITEM_NOT_FOUND)
    return item


class DealItemService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._deals = DealRepository(db)
        self._deal_service = DealService(db, registry)
        self._product_items = DealProductItemService(db, registry)
        self._activity_logs = ActivityLogService(db)

    def add(self, deal_id: UUID, payload: DealItemCreate, actor: User) -> DealRead:
        deal = self._deal_service.get_owned_draft(deal_id, actor)
        if len(deal.items) >= MAX_DEAL_ITEMS:
            raise BusinessRuleError(DealMessages.TOO_MANY_ITEMS.format(limit=MAX_DEAL_ITEMS))
        _ensure_image_in_deal(deal, payload.image_id)
        next_position = max((item.sort_order for item in deal.items), default=-1) + 1
        [item] = self._product_items.build_items(
            deal.business_id,
            [payload],
            next_position,
            [item.product_id for item in deal.items if item.product_id],
        )
        deal.items.append(item)
        saved = self._deals.save(deal)
        self._log(actor, ActivityAction.DEAL_ITEM_ADDED, item.id, deal.id)
        return DealRead.from_deal(saved, actor)

    def update(
        self, deal_id: UUID, item_id: UUID, payload: DealItemUpdate, actor: User
    ) -> DealRead:
        deal = self._deal_service.get_owned_draft(deal_id, actor)
        item = _find_item(deal, item_id)
        changes = {
            field: value
            for field, value in payload.model_dump(exclude_unset=True).items()
            if value is not None or field in CLEARABLE_FIELDS
        }
        if item.product_id is not None and PRODUCT_LOCKED_FIELDS & changes.keys():
            raise BusinessRuleError(DealMessages.PRODUCT_ITEM_FIELDS_LOCKED)
        if item.product_id is not None:
            if "deal_price" in changes and changes["deal_price"] is None:
                raise BusinessRuleError(DealMessages.PRODUCT_DEAL_PRICE_REQUIRED)
            if "quantity" in changes and changes["quantity"] is None:
                raise BusinessRuleError(DealMessages.PRODUCT_QUANTITY_REQUIRED)
        _ensure_image_in_deal(deal, changes.get("image_id"))
        try:
            ensure_price_order(
                changes.get("original_price", item.original_price),
                changes.get("deal_price", item.deal_price),
            )
        except ValueError as exc:
            raise BusinessRuleError(str(exc)) from exc
        for field, value in changes.items():
            setattr(item, field, value)
        saved = self._deals.save(deal)
        self._log(
            actor,
            ActivityAction.DEAL_ITEM_UPDATED,
            item_id,
            deal.id,
            {"updated_fields": list(changes)},
        )
        return DealRead.from_deal(saved, actor)

    def remove(self, deal_id: UUID, item_id: UUID, actor: User) -> DealRead:
        deal = self._deal_service.get_owned_draft(deal_id, actor)
        deal.items.remove(_find_item(deal, item_id))
        saved = self._deals.save(deal)
        self._log(actor, ActivityAction.DEAL_ITEM_REMOVED, item_id, deal.id)
        return DealRead.from_deal(saved, actor)

    def _log(
        self,
        actor: User,
        action: str,
        item_id: UUID,
        deal_id: UUID,
        extra: dict[str, object] | None = None,
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=item_id,
            metadata={"deal_id": str(deal_id), **(extra or {})},
        )
