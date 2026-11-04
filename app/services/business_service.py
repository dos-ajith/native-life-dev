from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.core.messages import BusinessMessages, UserMessages
from app.core.permissions import PermissionName, RoleSlug
from app.core.timezone import app_now
from app.models.business import Business, BusinessStatus, BusinessVerificationStatus
from app.models.business_document import BusinessDocument
from app.models.business_image import BusinessImage
from app.models.user import User, UserStatus
from app.repositories.business_repository import BusinessDiscoveryRow, BusinessRepository
from app.repositories.gis_village_repository import GisVillageRepository
from app.repositories.spatial import point_from_coordinates
from app.repositories.user_repository import UserRepository
from app.schemas.account_role import AccountRoleVerificationStatus
from app.schemas.business import (
    BusinessCreate,
    BusinessDiscoveryQuery,
    BusinessLocationInput,
    BusinessSummaryRead,
    BusinessUpdate,
)
from app.schemas.category import CategoryRef, CategoryWithParentRead
from app.schemas.pagination import PaginationParams
from app.services.account_role_status_service import AccountRoleStatusService
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.business_attachment_storage import (
    BusinessUploads,
    StagedAttachments,
    discard_business_attachments,
    stage_business_attachments,
)
from app.services.category_service import CategoryService
from app.services.notification_service import NotificationService
from app.services.user_native_place_service import UserNativePlaceService

ENTITY_TYPE = "business"
IMAGE_ENTITY_TYPE = "business_image"
DOCUMENT_ENTITY_TYPE = "business_document"
AI_DISCOVERY_MAX_RESULTS = 10
METERS_PER_KM = 1000


def _to_summary(row: BusinessDiscoveryRow) -> BusinessSummaryRead:
    parent = (
        CategoryRef(id=row.parent_category_id, name=row.parent_category_name)
        if row.parent_category_id is not None and row.parent_category_name is not None
        else None
    )
    return BusinessSummaryRead(
        id=row.id,
        name=row.name,
        description=row.description,
        category=CategoryWithParentRead(id=row.category_id, name=row.category_name, parent=parent),
        distance_meters=round(row.distance_meters) if row.distance_meters is not None else None,
        image_url=row.image_url,
    )


def _location_from(payload: BusinessLocationInput) -> Any | None:
    if payload.latitude is None or payload.longitude is None:
        return None
    return point_from_coordinates(payload.latitude, payload.longitude)


@dataclass(frozen=True)
class CreatedBusiness:
    business: Business
    images: list[BusinessImage]
    documents: list[BusinessDocument]


class BusinessService:
    def __init__(self, db: Session) -> None:
        self._businesses = BusinessRepository(db)
        self._categories = CategoryService(db)
        self._native_places = UserNativePlaceService(db)
        self._account_roles = AccountRoleStatusService(db)
        self._users = UserRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._villages = GisVillageRepository(db)
        self._notifications = NotificationService(db)

    def _notify_reviewers(self, business: Business, actor: User) -> None:
        village = None
        if business.latitude is not None and business.longitude is not None:
            village = self._villages.find_containing_point(business.latitude, business.longitude)
        self._notifications.notify_business_submitted(
            actor,
            business.id,
            business.name,
            village.native_admin_id if village is not None else None,
        )

    def create(
        self,
        payload: BusinessCreate,
        uploads: BusinessUploads,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> CreatedBusiness:
        self._ensure_can_create(actor)
        self._ensure_name_available(actor.id, payload.name)
        self._categories.ensure_assignable(payload.category_id)
        created = self._persist(
            Business(
                owner_id=actor.id,
                category_id=payload.category_id,
                name=payload.name,
                description=payload.description,
                location=_location_from(payload),
                status=BusinessStatus.INACTIVE,
                verification_status=BusinessVerificationStatus.PENDING,
            ),
            payload,
            uploads,
            actor,
            ip_address,
            user_agent,
        )
        self._notify_reviewers(created.business, actor)
        return created

    def create_for_owner(
        self,
        payload: BusinessCreate,
        uploads: BusinessUploads,
        owner_id: UUID,
        admin: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> CreatedBusiness:
        owner = self._users.get_by_id(owner_id)
        if owner is None:
            raise NotFoundError(UserMessages.NOT_FOUND)
        if owner.status != UserStatus.ACTIVE or not has_permission(
            owner, PermissionName.BUSINESS_CREATE
        ):
            raise BusinessRuleError(BusinessMessages.OWNER_NOT_BUSINESS_USER)
        self._ensure_name_available(owner.id, payload.name)
        self._categories.ensure_assignable(payload.category_id)
        return self._persist(
            Business(
                owner_id=owner.id,
                category_id=payload.category_id,
                name=payload.name,
                description=payload.description,
                location=_location_from(payload),
                status=BusinessStatus.ACTIVE,
                verification_status=BusinessVerificationStatus.VERIFIED,
                reviewed_by=admin.id,
                reviewed_at=app_now(),
            ),
            payload,
            uploads,
            admin,
            ip_address,
            user_agent,
        )

    def _persist(
        self,
        business: Business,
        payload: BusinessCreate,
        uploads: BusinessUploads,
        actor: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> CreatedBusiness:
        staged = stage_business_attachments(uploads, payload.document_types)
        try:
            saved = self._businesses.add_with_attachments(business, staged.images, staged.documents)
        except Exception:
            self._businesses.rollback()
            discard_business_attachments(staged, uploads)
            raise
        self._log_created(saved, staged, actor, ip_address, user_agent)
        return CreatedBusiness(saved, staged.images, staged.documents)

    def _ensure_name_available(
        self, owner_id: UUID, name: str, excluding_id: UUID | None = None
    ) -> None:
        if self._businesses.owner_has_named(owner_id, name, excluding_id):
            raise ConflictError(BusinessMessages.NAME_ALREADY_USED)

    def _ensure_can_create(self, actor: User) -> None:
        if has_permission(actor, PermissionName.BUSINESS_CREATE):
            return
        state = self._account_roles.state_for(actor.id)
        awaiting_approval = (
            state is not None
            and state.role.slug == RoleSlug.BUSINESS_SERVICE_PROVIDER
            and state.verification_status == AccountRoleVerificationStatus.PENDING
        )
        if not awaiting_approval:
            raise AuthorizationError(BusinessMessages.ROLE_NOT_VERIFIED)
        self._ensure_no_other_pending_review(actor)

    def _ensure_no_other_pending_review(self, actor: User) -> None:
        if has_permission(actor, PermissionName.BUSINESS_CREATE):
            return
        if self._businesses.has_pending_verification_for_owner(actor.id):
            raise BusinessRuleError(BusinessMessages.PENDING_REVIEW_EXISTS)

    def _ensure_can_publish(self, business: Business, actor: User) -> None:
        if business.verification_status != BusinessVerificationStatus.VERIFIED:
            raise BusinessRuleError(BusinessMessages.NOT_VERIFIED)
        if has_permission(actor, PermissionName.BUSINESS_UPDATE_ANY):
            return
        if business.owner_id == actor.id and has_permission(actor, PermissionName.BUSINESS_CREATE):
            return
        raise BusinessRuleError(BusinessMessages.PUBLISH_REQUIRES_VERIFIED_ROLE)

    def _log_created(
        self,
        business: Business,
        staged: StagedAttachments,
        actor: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.BUSINESS_CREATED,
            entity_type=ENTITY_TYPE,
            entity_id=business.id,
            metadata={
                "status": business.status.value,
                "category_id": str(business.category_id),
                "owner_id": str(business.owner_id),
                "image_count": len(staged.images),
                "document_count": len(staged.documents),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        for image in staged.images:
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.BUSINESS_IMAGE_ADDED,
                entity_type=IMAGE_ENTITY_TYPE,
                entity_id=image.id,
                metadata={"business_id": str(business.id)},
            )
        for document in staged.documents:
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.BUSINESS_DOCUMENT_ADDED,
                entity_type=DOCUMENT_ENTITY_TYPE,
                entity_id=document.id,
                metadata={
                    "business_id": str(business.id),
                    "document_type": document.document_type,
                },
            )

    def get(self, business_id: UUID) -> Business:
        business = self._businesses.get_by_id(business_id)
        if business is None:
            raise NotFoundError(BusinessMessages.NOT_FOUND)
        return business

    def get_active(self, business_id: UUID) -> Business:
        business = self.get(business_id)
        if business.status != BusinessStatus.ACTIVE:
            raise BusinessRuleError(BusinessMessages.INACTIVE)
        return business

    def get_for_actor(self, business_id: UUID, actor: User) -> Business:
        business = self.get(business_id)
        self._ensure_owner_or_permission(business, actor, PermissionName.BUSINESS_VIEW_ANY)
        return business

    def list_own(self, actor: User, params: PaginationParams) -> tuple[list[Business], int]:
        return self._businesses.list_by_owner(actor.id, params)

    def discover(
        self, query: BusinessDiscoveryQuery, params: PaginationParams
    ) -> tuple[list[BusinessSummaryRead], int]:
        rows, total = self._businesses.search_active(query, params)
        return [_to_summary(row) for row in rows], total

    def search_nearby(
        self, query: BusinessDiscoveryQuery, params: PaginationParams, actor: User
    ) -> tuple[list[BusinessSummaryRead], int]:
        return self.discover(self._with_default_area(query, actor), params)

    def _with_default_area(
        self, query: BusinessDiscoveryQuery, actor: User
    ) -> BusinessDiscoveryQuery:
        if query.has_location or query.village_id is not None:
            return query
        area = self._native_places.default_nearby_area(actor)
        if area is None:
            return query
        return query.model_copy(
            update={
                "latitude": area.latitude,
                "longitude": area.longitude,
                "radius_meters": round(area.radius_km * METERS_PER_KM),
            }
        )

    def search_for_ai(
        self, query: BusinessDiscoveryQuery, limit: int
    ) -> tuple[list[BusinessSummaryRead], int]:
        bounded = max(1, min(limit, AI_DISCOVERY_MAX_RESULTS))
        return self.discover(query, PaginationParams(page=1, page_size=bounded))

    def resubmit(
        self,
        business_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Business:
        business = self.get(business_id)
        if business.owner_id != actor.id:
            raise AuthorizationError(BusinessMessages.NOT_OWNER)
        if business.verification_status != BusinessVerificationStatus.REJECTED:
            raise BusinessRuleError(BusinessMessages.NOT_REJECTED)
        self._ensure_no_other_pending_review(actor)
        business.verification_status = BusinessVerificationStatus.PENDING
        business.resubmission_count += 1
        business.reviewed_by = None
        business.reviewed_at = None
        business.review_note = None
        business.escalated_at = None
        business.escalated_by = None
        business.escalation_note = None
        saved = self._businesses.save(business)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.BUSINESS_RESUBMITTED,
            entity_type=ENTITY_TYPE,
            entity_id=saved.id,
            metadata={"resubmission_count": saved.resubmission_count},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._notify_reviewers(saved, actor)
        return saved

    def update(
        self,
        business_id: UUID,
        payload: BusinessUpdate,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Business:
        business = self.get(business_id)
        self.ensure_can_modify(business, actor, PermissionName.BUSINESS_UPDATE_ANY)
        data = payload.model_dump(exclude_none=True, exclude={"latitude", "longitude"})
        if data.get("status") == BusinessStatus.ACTIVE and business.status != BusinessStatus.ACTIVE:
            self._ensure_can_publish(business, actor)
        if "category_id" in data and data["category_id"] != business.category_id:
            self._categories.ensure_assignable(data["category_id"])
        if "name" in data:
            self._ensure_name_available(business.owner_id, data["name"], business.id)
        for field, value in data.items():
            setattr(business, field, value)
        location = _location_from(payload)
        updated_fields = list(data.keys())
        if location is not None:
            business.location = location
            updated_fields.append("location")
        saved = self._businesses.save(business)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.BUSINESS_UPDATED,
            entity_type=ENTITY_TYPE,
            entity_id=business.id,
            metadata={"updated_fields": updated_fields},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return saved

    def delete(
        self,
        business_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        business = self.get(business_id)
        self.ensure_can_modify(business, actor, PermissionName.BUSINESS_DELETE_ANY)
        self._businesses.soft_delete(business)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.BUSINESS_DELETED,
            entity_type=ENTITY_TYPE,
            entity_id=business.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def ensure_can_modify(self, business: Business, actor: User, override_permission: str) -> None:
        self._ensure_owner_or_permission(business, actor, override_permission)

    def _ensure_owner_or_permission(self, business: Business, actor: User, permission: str) -> None:
        if business.owner_id != actor.id and not has_permission(actor, permission):
            raise AuthorizationError(BusinessMessages.NOT_OWNER)
