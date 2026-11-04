from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import BusinessMessages, CategoryMessages
from app.core.permissions import PermissionName
from app.core.timezone import app_now
from app.models.category import Category, CategoryStatus
from app.models.user import User
from app.realtime.publisher import RealtimePublisher
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.notification_service import NotificationService
from app.utils.slug import build_unique_slug, slugify

ENTITY_TYPE = "category"


def build_category_slug(categories: CategoryRepository, name: str, category_id: UUID) -> str:
    slug = slugify(name)
    if slug and not categories.slug_exists(slug):
        return slug
    return build_unique_slug(name, category_id)


def _is_usable(category: Category) -> bool:
    return category.status == CategoryStatus.PUBLISHED and category.is_active


def _chain_is_usable(chain: list[Category]) -> bool:
    return all(_is_usable(item) for item in chain)


class CategoryService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._db = db
        self._publisher = publisher
        self._categories = CategoryRepository(db)
        self._activity_logs = ActivityLogService(db)

    def create(self, payload: CategoryCreate, actor: User) -> Category:
        category = self._add_validated(payload, actor, CategoryStatus.PUBLISHED, is_active=True)
        self._log(actor, ActivityAction.CATEGORY_CREATED, category)
        return category

    def suggest(self, payload: CategoryCreate, actor: User) -> Category:
        category = self._add_validated(payload, actor, CategoryStatus.PENDING, is_active=False)
        self._log(actor, ActivityAction.CATEGORY_SUGGESTED, category)
        self._notifications().notify_category_suggested(actor, category.id, category.name)
        return category

    def get(self, category_id: UUID) -> Category:
        category = self._categories.get_by_id(category_id)
        if category is None:
            raise NotFoundError(CategoryMessages.NOT_FOUND)
        return category

    def list_by_parent(
        self,
        parent_id: UUID | None,
        params: PaginationParams,
        viewer: User,
        include_inactive: bool = False,
        parent_slug: str | None = None,
    ) -> tuple[list[Category], int]:
        if include_inactive and not has_permission(viewer, PermissionName.CATEGORY_UPDATE):
            raise AuthorizationError(CategoryMessages.INACTIVE_LIST_FORBIDDEN)
        if parent_slug is not None:
            if parent_id is not None:
                raise BusinessRuleError(CategoryMessages.PARENT_FILTER_CONFLICT)
            by_slug = self._categories.get_by_slug(parent_slug.strip().lower())
            if by_slug is None:
                raise NotFoundError(CategoryMessages.NOT_FOUND)
            parent_id = by_slug.id
        if parent_id is not None:
            parent = self.get(parent_id)
            if parent.status != CategoryStatus.PUBLISHED:
                raise NotFoundError(CategoryMessages.NOT_FOUND)
            if not include_inactive and not _chain_is_usable(self._categories.get_chain(parent_id)):
                raise NotFoundError(CategoryMessages.NOT_FOUND)
        return self._categories.list_by_parent(parent_id, params, include_inactive)

    def list_pending(self, params: PaginationParams) -> tuple[list[Category], int]:
        return self._categories.list_pending(params)

    def search_active(self, query: str, limit: int) -> list[Category]:
        return self._categories.search_active(query, limit)

    def ensure_assignable(self, category_id: UUID) -> Category:
        category, _ = self._assignable_chain(category_id)
        return category

    def ensure_assignable_under(self, category_id: UUID, root_name: str) -> Category:
        category, chain = self._assignable_chain(category_id)
        root = next(item for item in chain if item.parent_id is None)
        if root.name.casefold() != root_name.casefold():
            raise BusinessRuleError(CategoryMessages.OUTSIDE_ROOT.format(root=root_name))
        return category

    def _assignable_chain(self, category_id: UUID) -> tuple[Category, list[Category]]:
        chain = self._categories.get_chain(category_id)
        category = next((item for item in chain if item.id == category_id), None)
        if category is None or not _chain_is_usable(chain):
            raise BusinessRuleError(BusinessMessages.INVALID_CATEGORY)
        return category, chain

    def approve(self, category_id: UUID, admin: User) -> Category:
        category = self._get_pending(category_id)
        if category.parent_id is not None:
            self._ensure_usable_parent(category.parent_id)
        category.status = CategoryStatus.PUBLISHED
        category.is_active = True
        self._mark_reviewed(category, admin, None)
        saved = self._categories.save(category)
        self._log(admin, ActivityAction.CATEGORY_APPROVED, saved)
        if saved.created_by is not None:
            self._notifications().notify_category_approved(
                saved.created_by, admin, saved.id, saved.name
            )
        return saved

    def reject(self, category_id: UUID, admin: User, review_note: str) -> Category:
        category = self._get_pending(category_id)
        category.status = CategoryStatus.REJECTED
        category.is_active = False
        self._mark_reviewed(category, admin, review_note)
        saved = self._categories.save(category)
        self._log(admin, ActivityAction.CATEGORY_REJECTED, saved)
        if saved.created_by is not None:
            self._notifications().notify_category_rejected(
                saved.created_by, admin, saved.id, saved.name, review_note
            )
        return saved

    def update(self, category_id: UUID, payload: CategoryUpdate, actor: User) -> Category:
        category = self.get(category_id)
        changes = payload.model_dump(exclude={"parent_id", "is_active"}, exclude_none=True)
        parent_changes = "parent_id" in payload.model_fields_set
        new_parent_id = payload.parent_id if parent_changes else category.parent_id
        new_name = payload.name or category.name
        activation_changed = (
            payload.is_active is not None and payload.is_active != category.is_active
        )

        if activation_changed and category.status != CategoryStatus.PUBLISHED:
            raise BusinessRuleError(CategoryMessages.NOT_PUBLISHED)
        if new_parent_id != category.parent_id:
            self._ensure_can_move_under(category, new_parent_id)
        if payload.is_active is True and activation_changed and new_parent_id is not None:
            self._ensure_usable_parent(new_parent_id)
        renamed_or_moved = new_parent_id != category.parent_id or new_name != category.name
        if renamed_or_moved and category.status != CategoryStatus.REJECTED:
            self._ensure_name_available(new_parent_id, new_name, category.id)

        for field, value in changes.items():
            setattr(category, field, value)
        category.parent_id = new_parent_id
        if activation_changed:
            category.is_active = bool(payload.is_active)
        saved = self._categories.save(category)

        updated_fields = [*changes, *(["parent_id"] if parent_changes else [])]
        if updated_fields:
            self._log(
                actor,
                ActivityAction.CATEGORY_UPDATED,
                saved,
                {"updated_fields": updated_fields},
            )
        if activation_changed:
            action = (
                ActivityAction.CATEGORY_ACTIVATED
                if saved.is_active
                else ActivityAction.CATEGORY_DEACTIVATED
            )
            self._log(actor, action, saved)
        return saved

    def delete(self, category_id: UUID, actor: User) -> None:
        category = self.get(category_id)
        if self._categories.has_children(category.id):
            raise BusinessRuleError(CategoryMessages.HAS_CHILDREN)
        if self._categories.is_used_by_businesses(category.id):
            raise BusinessRuleError(CategoryMessages.IN_USE)
        if self._categories.is_bound_to_plugins(category.id):
            raise BusinessRuleError(CategoryMessages.BOUND_TO_PLUGIN)
        self._categories.delete(category)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.CATEGORY_DELETED,
            entity_type=ENTITY_TYPE,
            entity_id=category_id,
        )

    def _add_validated(
        self, payload: CategoryCreate, actor: User, status: CategoryStatus, is_active: bool
    ) -> Category:
        if payload.parent_id is not None:
            self._ensure_usable_parent(payload.parent_id)
        self._ensure_name_available(payload.parent_id, payload.name)
        category_id = uuid4()
        return self._categories.add(
            Category(
                id=category_id,
                parent_id=payload.parent_id,
                name=payload.name,
                slug=build_category_slug(self._categories, payload.name, category_id),
                description=payload.description,
                status=status,
                is_active=is_active,
                created_by=actor.id,
            )
        )

    def _notifications(self) -> NotificationService:
        return NotificationService(self._db, self._publisher)

    def _get_pending(self, category_id: UUID) -> Category:
        category = self.get(category_id)
        if category.status != CategoryStatus.PENDING:
            raise BusinessRuleError(CategoryMessages.NOT_PENDING)
        return category

    def _mark_reviewed(self, category: Category, reviewer: User, review_note: str | None) -> None:
        category.reviewed_by = reviewer.id
        category.reviewed_at = app_now()
        category.review_note = review_note

    def _log(
        self,
        actor: User,
        action: str,
        category: Category,
        extra: dict[str, object] | None = None,
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=category.id,
            metadata={"name": category.name, **(extra or {})},
        )

    def _ensure_usable_parent(self, parent_id: UUID) -> None:
        chain = self._categories.get_chain(parent_id)
        if not any(item.id == parent_id for item in chain):
            raise BusinessRuleError(CategoryMessages.PARENT_NOT_FOUND)
        if not _chain_is_usable(chain):
            raise BusinessRuleError(CategoryMessages.PARENT_INACTIVE)

    def _ensure_can_move_under(self, category: Category, new_parent_id: UUID | None) -> None:
        if new_parent_id is None:
            return
        if new_parent_id == category.id:
            raise BusinessRuleError(CategoryMessages.SELF_PARENT)
        chain = self._categories.get_chain(new_parent_id)
        if not any(item.id == new_parent_id for item in chain):
            raise BusinessRuleError(CategoryMessages.PARENT_NOT_FOUND)
        if any(item.id == category.id for item in chain):
            raise BusinessRuleError(CategoryMessages.CIRCULAR_HIERARCHY)
        if _is_usable(category) and not _chain_is_usable(chain):
            raise BusinessRuleError(CategoryMessages.PARENT_INACTIVE)

    def _ensure_name_available(
        self, parent_id: UUID | None, name: str, exclude_id: UUID | None = None
    ) -> None:
        if self._categories.exists_with_name(parent_id, name, exclude_id):
            raise BusinessRuleError(CategoryMessages.DUPLICATE_NAME)
