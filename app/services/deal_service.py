from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.core.messages import DealMessages
from app.core.timezone import to_naive_app_time
from app.models.deal import DEALS_ROOT_CATEGORY_NAME, Deal, DealStatus
from app.models.deal_native import DealNative
from app.models.order import DeliveryOption
from app.models.user import User
from app.models.user_native_place import NativePlaceSlot
from app.plugins.registry import PluginRegistry
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_participant_repository import DealParticipantRepository
from app.repositories.deal_repository import DealExploreFilter, DealRepository
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.deal import (
    DealCreate,
    DealExploreQuery,
    DealRead,
    DealUpdate,
    ensure_delivery_options_valid,
    ensure_end_after_start,
)
from app.schemas.delivery import DeliveryOptionRead
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService
from app.services.category_service import CategoryService
from app.services.deal_access_policy import DealAccessPolicy, ensure_draft, get_deal
from app.services.deal_delivery_service import DealDeliveryService
from app.services.deal_eligibility_service import DealEligibilityService
from app.services.deal_expiry_service import DealExpiryService, deal_clock_now
from app.services.deal_image_storage import discard_deal_images, store_deal_images
from app.services.deal_product_item_service import DealProductItemService

ENTITY_TYPE = "deal"
CLEARABLE_FIELDS = frozenset(
    {
        "description",
        "business_id",
        "valid_until",
        "min_joiners",
        "pickup_location",
        "delivery_details",
    }
)
DATETIME_FIELDS = ("starts_at", "valid_until")


class DealContentValidator:
    def __init__(self, db: Session) -> None:
        self._categories = CategoryService(db)
        self._businesses = BusinessService(db)
        self._places = UserNativePlaceRepository(db)
        self._eligibility = DealEligibilityService(db)

    def ensure_category(self, category_id: UUID) -> None:
        self._categories.ensure_assignable_under(category_id, DEALS_ROOT_CATEGORY_NAME)

    def ensure_can_promote_business(self, business_id: UUID, actor: User) -> None:
        business = self._businesses.get_active(business_id)
        if business.owner_id == actor.id:
            return
        if not self._eligibility.holds_accepting_role(actor):
            raise AuthorizationError(DealMessages.BUSINESS_NOT_OWNED)
        promoter_place = self._places.get_by_slot(actor.id, NativePlaceSlot.PRIMARY)
        owner_place = self._places.get_by_slot(business.owner_id, NativePlaceSlot.PRIMARY)
        if (
            promoter_place is None
            or owner_place is None
            or promoter_place.village_id != owner_place.village_id
        ):
            raise AuthorizationError(DealMessages.BUSINESS_NOT_OWNED)

    def primary_village_id(self, actor: User) -> UUID:
        primary = self._places.get_by_slot(actor.id, NativePlaceSlot.PRIMARY)
        if primary is None:
            raise BusinessRuleError(DealMessages.PRIMARY_NATIVE_REQUIRED)
        return primary.village_id


class DealService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._product_items = DealProductItemService(db, registry)
        self._deals = DealRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._participants = DealParticipantRepository(db)
        self._delivery = DealDeliveryService(db)
        self._places = UserNativePlaceRepository(db)
        self._content = DealContentValidator(db)
        self._access = DealAccessPolicy(db)
        self._expiry = DealExpiryService(db)
        self._activity_logs = ActivityLogService(db)

    def create(
        self,
        payload: DealCreate,
        files: list[UploadFile],
        private_upload_dir: str,
        actor: User,
    ) -> DealRead:
        if any(item.image_id is not None for item in payload.items):
            raise NotFoundError(DealMessages.IMAGE_NOT_FOUND)
        village_id = self._content.primary_village_id(actor)
        self._content.ensure_category(payload.category_id)
        if payload.business_id is not None:
            self._content.ensure_can_promote_business(payload.business_id, actor)
        items = self._product_items.build_items(payload.business_id, payload.items)
        images = store_deal_images(files, private_upload_dir)
        try:
            deal = self._deals.add(
                Deal(
                    created_by=actor.id,
                    business_id=payload.business_id,
                    category_id=payload.category_id,
                    name=payload.name,
                    description=payload.description,
                    min_joiners=payload.min_joiners,
                    pickup_location=payload.pickup_location,
                    delivery_details=payload.delivery_details,
                    delivery_options=[option.value for option in payload.delivery_options],
                    starts_at=_naive(payload.starts_at),
                    valid_until=_naive(payload.valid_until),
                    natives=[DealNative(village_id=village_id, is_primary=True)],
                    items=items,
                    images=images,
                )
            )
        except Exception:
            self._db.rollback()
            discard_deal_images(images)
            raise
        self._log(
            actor,
            ActivityAction.DEAL_CREATED,
            deal.id,
            {
                "category_id": str(deal.category_id),
                "business_id": str(deal.business_id) if deal.business_id else None,
                "item_count": len(deal.items),
                "image_count": len(deal.images),
            },
        )
        return DealRead.from_deal(deal, actor)

    def get_read(self, deal_id: UUID, viewer: User) -> DealRead:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_view(deal, viewer)
        joined = self._participants.joined_deal_ids(viewer.id, [deal.id])
        return DealRead.from_deal(deal, viewer, has_joined=deal.id in joined)

    def delivery_options(self, deal_id: UUID, viewer: User) -> list[DeliveryOptionRead]:
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_view(deal, viewer)
        return self._delivery.options_for(deal, deal_clock_now())

    def list_mine(
        self, actor: User, status: DealStatus | None, params: PaginationParams
    ) -> tuple[list[DealRead], int]:
        self._expiry.expire_overdue()
        deals, total = self._deals.list_by_creator(actor.id, status, params)
        return [DealRead.from_deal(deal, actor) for deal in deals], total

    def update(self, deal_id: UUID, payload: DealUpdate, actor: User) -> DealRead:
        deal = self.get_owned_draft(deal_id, actor)
        data = payload.model_dump(exclude_unset=True)
        changes = {
            field: value
            for field, value in data.items()
            if value is not None or field in CLEARABLE_FIELDS
        }
        if "business_id" in changes and changes["business_id"] != deal.business_id and deal.items:
            raise BusinessRuleError(DealMessages.BUSINESS_LOCKED_BY_ITEMS)
        if "category_id" in changes and changes["category_id"] != deal.category_id:
            self._content.ensure_category(changes["category_id"])
        if changes.get("business_id") is not None and changes["business_id"] != deal.business_id:
            self._content.ensure_can_promote_business(changes["business_id"], actor)
        self._ensure_consistent(deal, changes)
        for field in DATETIME_FIELDS:
            if field in changes:
                changes[field] = _naive(changes[field])
        if "delivery_options" in changes:
            changes["delivery_options"] = [option.value for option in changes["delivery_options"]]
        for field, value in changes.items():
            setattr(deal, field, value)
        saved = self._deals.save(deal)
        self._log(actor, ActivityAction.DEAL_UPDATED, deal.id, {"updated_fields": list(changes)})
        return DealRead.from_deal(saved, actor)

    def delete(self, deal_id: UUID, actor: User) -> None:
        deal = self.get_owned_draft(deal_id, actor)
        deal.deleted_at = deal_clock_now()
        self._db.commit()
        self._log(actor, ActivityAction.DEAL_DELETED, deal_id)

    def cancel(self, deal_id: UUID, actor: User) -> DealRead:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_owner(deal, actor)
        previous_status = deal.status
        if not self._deals.cancel(deal.id):
            self._db.rollback()
            raise ConflictError(DealMessages.NOT_CANCELLABLE)
        self._invitations.close_open([deal.id])
        self._db.commit()
        self._log(
            actor,
            ActivityAction.DEAL_CANCELLED,
            deal_id,
            {"previous_status": previous_status.value},
        )
        return DealRead.from_deal(get_deal(self._deals, deal_id), actor)

    def close(self, deal_id: UUID, actor: User) -> DealRead:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_owner(deal, actor)
        if not self._deals.close(deal.id):
            self._db.rollback()
            raise ConflictError(DealMessages.NOT_CLOSABLE)
        self._db.commit()
        self._log(actor, ActivityAction.DEAL_CLOSED, deal_id)
        return DealRead.from_deal(get_deal(self._deals, deal_id), actor)

    def explore(
        self, viewer: User, query: DealExploreQuery, params: PaginationParams
    ) -> tuple[list[DealRead], int]:
        deals, total = self._deals.list_published_in_village(
            DealExploreFilter(
                now=deal_clock_now(),
                village_id=query.village_id or self._native_village_id(viewer, query.native),
                category_id=query.category_id,
                search=query.search,
            ),
            params,
        )
        joined = self._participants.joined_deal_ids(viewer.id, [deal.id for deal in deals])
        return [
            DealRead.from_deal(deal, viewer, has_joined=deal.id in joined) for deal in deals
        ], total

    def _native_village_id(self, viewer: User, slot: NativePlaceSlot) -> UUID:
        place = self._places.get_by_slot(viewer.id, slot)
        if place is None:
            message = (
                DealMessages.PRIMARY_NATIVE_REQUIRED
                if slot == NativePlaceSlot.PRIMARY
                else DealMessages.SECONDARY_NATIVE_NOT_SET
            )
            raise BusinessRuleError(message)
        return place.village_id

    @staticmethod
    def _ensure_consistent(deal: Deal, changes: dict[str, Any]) -> None:
        try:
            ensure_end_after_start(
                changes.get("starts_at", deal.starts_at),
                changes.get("valid_until", deal.valid_until),
            )
        except ValueError as exc:
            raise BusinessRuleError(str(exc)) from exc
        pickup_location = changes.get("pickup_location", deal.pickup_location)
        delivery_details = changes.get("delivery_details", deal.delivery_details)
        if pickup_location is None and delivery_details is None:
            raise BusinessRuleError(DealMessages.PICKUP_OR_DELIVERY_REQUIRED)
        delivery_options = [
            DeliveryOption(option)
            for option in changes.get("delivery_options", deal.delivery_options)
        ]
        try:
            ensure_delivery_options_valid(delivery_options, pickup_location)
        except ValueError as exc:
            raise BusinessRuleError(str(exc)) from exc

    def get_owned_draft(self, deal_id: UUID, actor: User) -> Deal:
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_owner(deal, actor)
        ensure_draft(deal)
        return deal

    def _log(
        self,
        actor: User,
        action: str,
        deal_id: UUID,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=deal_id,
            metadata=metadata,
        )


def _naive(value: datetime | None) -> datetime | None:
    return to_naive_app_time(value) if value is not None else None
