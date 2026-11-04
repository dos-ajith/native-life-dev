import csv
import io
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import BusinessMessages
from app.core.permissions import RoleSlug
from app.core.timezone import app_now
from app.models.business import Business, BusinessStatus, BusinessVerificationStatus
from app.models.business_document import BusinessDocument, BusinessDocumentStatus
from app.models.business_image import BusinessImage
from app.models.user import User
from app.repositories.business_document_repository import BusinessDocumentRepository
from app.repositories.business_image_repository import BusinessImageRepository
from app.repositories.business_repository import BusinessCounts, BusinessRepository
from app.repositories.gis_village_repository import GisVillageRepository
from app.schemas.business import BusinessCreate
from app.schemas.business_review import BusinessReviewQuery
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import is_super_admin
from app.services.business_attachment_storage import BusinessUploads
from app.services.business_service import BusinessService, CreatedBusiness
from app.services.notification_service import NotificationService

ENTITY_TYPE = "business"
DOCUMENT_ENTITY_TYPE = "business_document"
EXPORT_COLUMNS = (
    "id",
    "name",
    "owner_name",
    "owner_email",
    "owner_phone",
    "category",
    "status",
    "verification_status",
    "escalated",
    "latitude",
    "longitude",
    "created_at",
)
SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(SPREADSHEET_FORMULA_PREFIXES) else text


@dataclass(frozen=True)
class BusinessForReview:
    business: Business
    images: list[BusinessImage]
    documents: list[BusinessDocument]


class BusinessVerificationService:
    def __init__(self, db: Session) -> None:
        self._businesses = BusinessRepository(db)
        self._business_service = BusinessService(db)
        self._documents = BusinessDocumentRepository(db)
        self._images = BusinessImageRepository(db)
        self._villages = GisVillageRepository(db)
        self._notifications = NotificationService(db)
        self._activity_logs = ActivityLogService(db)

    def list_for_review(
        self, query: BusinessReviewQuery, params: PaginationParams, admin: User
    ) -> tuple[list[Business], int]:
        return self._businesses.list_for_review(query, params, self._jurisdiction(admin))

    def create_for_owner(
        self,
        payload: BusinessCreate,
        uploads: BusinessUploads,
        owner_id: UUID,
        admin: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> CreatedBusiness:
        village_id = self._jurisdiction(admin)
        if village_id is not None and not self._is_inside(payload, village_id):
            raise BusinessRuleError(BusinessMessages.OUTSIDE_JURISDICTION)
        return self._business_service.create_for_owner(
            payload, uploads, owner_id, admin, ip_address, user_agent
        )

    def _is_inside(self, payload: BusinessCreate, village_id: UUID) -> bool:
        if payload.latitude is None or payload.longitude is None:
            return False
        return self._businesses.point_is_within_village(
            payload.latitude, payload.longitude, village_id
        )

    def export_csv(self, query: BusinessReviewQuery, admin: User) -> str:
        businesses = self._businesses.list_all_for_review(query, self._jurisdiction(admin))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(EXPORT_COLUMNS)
        for business in businesses:
            owner = business.owner
            writer.writerow(
                _csv_cell(value)
                for value in (
                    business.id,
                    business.name,
                    f"{owner.first_name} {owner.last_name}".strip(),
                    owner.email,
                    owner.phone,
                    business.category.name if business.category else None,
                    business.status.value,
                    business.verification_status.value,
                    business.escalated_at is not None,
                    business.latitude,
                    business.longitude,
                    business.created_at.isoformat(),
                )
            )
        return buffer.getvalue()

    def counts(self, admin: User) -> BusinessCounts:
        return self._businesses.count_for_review(self._jurisdiction(admin))

    def get_for_review(self, business_id: UUID, admin: User) -> BusinessForReview:
        business = self._get_in_jurisdiction(business_id, admin)
        return BusinessForReview(
            business=business,
            images=self._images.list_by_business(business.id),
            documents=self._documents.list_by_business(business.id),
        )

    def escalate(self, business_id: UUID, admin: User, escalation_note: str) -> Business:
        business = self._get_pending(business_id, admin)
        if business.escalated_at is not None:
            raise BusinessRuleError(BusinessMessages.ALREADY_ESCALATED)
        business.escalated_at = app_now()
        business.escalated_by = admin.id
        business.escalation_note = escalation_note
        saved = self._businesses.save(business)
        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.BUSINESS_ESCALATED,
            entity_type=ENTITY_TYPE,
            entity_id=saved.id,
            metadata={"owner_id": str(saved.owner_id)},
        )
        return saved

    def approve(self, business_id: UUID, admin: User) -> Business:
        business = self._get_resolvable(business_id, admin)
        business.verification_status = BusinessVerificationStatus.VERIFIED
        business.status = BusinessStatus.ACTIVE
        self._mark_reviewed(business, admin, None)
        saved = self._businesses.save(business)
        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.BUSINESS_APPROVED,
            entity_type=ENTITY_TYPE,
            entity_id=saved.id,
            metadata={"owner_id": str(saved.owner_id)},
        )
        self._notifications.notify_business_approved(saved.owner_id, admin, saved.id, saved.name)
        return saved

    def reject(self, business_id: UUID, admin: User, review_note: str) -> Business:
        business = self._get_resolvable(business_id, admin)
        business.verification_status = BusinessVerificationStatus.REJECTED
        business.status = BusinessStatus.INACTIVE
        self._mark_reviewed(business, admin, review_note)
        saved = self._businesses.save(business)
        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.BUSINESS_REJECTED,
            entity_type=ENTITY_TYPE,
            entity_id=saved.id,
            metadata={"owner_id": str(saved.owner_id)},
        )
        self._notifications.notify_business_rejected(
            saved.owner_id, admin, saved.id, saved.name, review_note
        )
        return saved

    def review_document(
        self,
        business_id: UUID,
        document_id: UUID,
        status: BusinessDocumentStatus,
        admin: User,
    ) -> BusinessDocument:
        business = self._get_in_jurisdiction(business_id, admin)
        document = self._get_document(business.id, document_id)
        document.status = status
        document.verified_at = app_now() if status == BusinessDocumentStatus.VERIFIED else None
        saved = self._documents.save(document)
        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.BUSINESS_DOCUMENT_REVIEWED,
            entity_type=DOCUMENT_ENTITY_TYPE,
            entity_id=saved.id,
            metadata={"business_id": str(business.id), "status": status.value},
        )
        return saved

    def get_document_for_review(
        self, business_id: UUID, document_id: UUID, admin: User
    ) -> BusinessDocument:
        business = self._get_in_jurisdiction(business_id, admin)
        return self._get_document(business.id, document_id)

    def _jurisdiction(self, admin: User) -> UUID | None:
        slugs = {role.slug for role in admin.approved_roles}
        if is_super_admin(admin) or RoleSlug.NATIVE_ADMIN not in slugs:
            return None
        village_id = self._villages.get_id_by_native_admin(admin.id)
        if village_id is None:
            raise BusinessRuleError(BusinessMessages.JURISDICTION_NOT_SET)
        return village_id

    def _get_in_jurisdiction(self, business_id: UUID, admin: User) -> Business:
        business = self._businesses.get_by_id(business_id)
        if business is None:
            raise NotFoundError(BusinessMessages.NOT_FOUND)
        village_id = self._jurisdiction(admin)
        if village_id is not None and not self._businesses.is_within_village(
            business.id, village_id
        ):
            raise NotFoundError(BusinessMessages.NOT_FOUND)
        return business

    def _get_pending(self, business_id: UUID, admin: User) -> Business:
        business = self._get_in_jurisdiction(business_id, admin)
        if business.verification_status != BusinessVerificationStatus.PENDING:
            raise BusinessRuleError(BusinessMessages.NOT_PENDING)
        return business

    def _get_resolvable(self, business_id: UUID, admin: User) -> Business:
        business = self._get_pending(business_id, admin)
        if business.escalated_at is not None and not is_super_admin(admin):
            raise AuthorizationError(BusinessMessages.ESCALATED_REQUIRES_SUPER_ADMIN)
        return business

    def _get_document(self, business_id: UUID, document_id: UUID) -> BusinessDocument:
        document = self._documents.get_by_id(document_id)
        if document is None or document.business_id != business_id:
            raise NotFoundError(BusinessMessages.DOCUMENT_NOT_FOUND)
        return document

    @staticmethod
    def _mark_reviewed(business: Business, admin: User, review_note: str | None) -> None:
        business.reviewed_by = admin.id
        business.reviewed_at = app_now()
        business.review_note = review_note
