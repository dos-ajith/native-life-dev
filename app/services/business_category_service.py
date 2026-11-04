from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.business_categories import (
    BUSINESS_TYPE_ROOT_SLUGS,
    CORE_BUSINESS_CATEGORIES,
    BusinessCategorySlug,
)
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import CategoryMessages
from app.models.category import Category, CategoryStatus
from app.models.plugin import PluginBusinessType
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.category_service import CategoryService

ENTITY_TYPE = "category"
TOP_LEVEL_LABEL = "the top level"


@dataclass(frozen=True)
class CoreBusinessCategories:
    by_slug: dict[str, Category]
    created: tuple[Category, ...]


def is_usable(category: Category) -> bool:
    return category.status == CategoryStatus.PUBLISHED and category.is_active


def ordered_chain(chain: Sequence[Category], leaf_id: UUID) -> list[Category]:
    by_id = {category.id: category for category in chain}
    ordered: list[Category] = []
    current = by_id.get(leaf_id)
    while current is not None:
        ordered.append(current)
        current = by_id.get(current.parent_id) if current.parent_id is not None else None
    return list(reversed(ordered))


def business_type_of(chain: Sequence[Category]) -> PluginBusinessType | None:
    slugs = [category.slug for category in chain]
    if not slugs or slugs[0] != BusinessCategorySlug.ROOT:
        return None
    return next(
        (
            business_type
            for business_type, slug in BUSINESS_TYPE_ROOT_SLUGS.items()
            if slug in slugs
        ),
        None,
    )


class BusinessCategoryService:
    def __init__(self, db: Session) -> None:
        self._categories = CategoryRepository(db)
        self._category_service = CategoryService(db)
        self._activity_logs = ActivityLogService(db)

    def ensure_core_categories(self) -> CoreBusinessCategories:
        by_slug: dict[str, Category] = {}
        created: list[Category] = []
        for slug, name, parent_slug in CORE_BUSINESS_CATEGORIES:
            parent = by_slug[parent_slug] if parent_slug is not None else None
            existing = self._categories.get_by_slug(slug)
            if existing is not None:
                self._ensure_matches(existing, slug, name, parent)
                by_slug[slug] = existing
                continue
            category = self._create(slug, name, parent)
            by_slug[slug] = category
            created.append(category)
        return CoreBusinessCategories(by_slug=by_slug, created=tuple(created))

    def list_children(
        self, parent_id: UUID | None, params: PaginationParams, viewer: User
    ) -> tuple[list[Category], int]:
        root = self._categories.get_by_slug(BusinessCategorySlug.ROOT)
        if root is None:
            raise NotFoundError(CategoryMessages.NOT_FOUND)
        if parent_id is not None and parent_id != root.id:
            chain = self._categories.get_chain(parent_id)
            if root.id not in {category.id for category in chain}:
                raise NotFoundError(CategoryMessages.NOT_FOUND)
        return self._category_service.list_by_parent(parent_id or root.id, params, viewer)

    def seed(self) -> list[Category]:
        result = self.ensure_core_categories()
        self._categories.commit()
        for category in result.created:
            self.log_created(category)
        return list(result.created)

    def log_created(self, category: Category) -> None:
        self._activity_logs.log(
            actor=None,
            action=ActivityAction.CATEGORY_CREATED,
            entity_type=ENTITY_TYPE,
            entity_id=category.id,
            metadata={"slug": category.slug, "parent_id": str(category.parent_id)},
        )

    def _create(self, slug: str, name: str, parent: Category | None) -> Category:
        parent_id = parent.id if parent is not None else None
        clash = self._categories.find_by_name(parent_id, name)
        if clash is not None:
            raise BusinessRuleError(
                CategoryMessages.CORE_CATEGORY_CONFLICT.format(
                    name=name, slug=clash.slug, expected=slug
                )
            )
        return self._categories.stage(
            Category(
                id=uuid4(),
                parent_id=parent_id,
                name=name,
                slug=slug,
                status=CategoryStatus.PUBLISHED,
                is_active=True,
            )
        )

    @staticmethod
    def _ensure_matches(existing: Category, slug: str, name: str, parent: Category | None) -> None:
        expected_parent_id = parent.id if parent is not None else None
        if existing.parent_id != expected_parent_id or existing.status != CategoryStatus.PUBLISHED:
            raise BusinessRuleError(
                CategoryMessages.CORE_CATEGORY_MISPLACED.format(
                    slug=slug, parent=parent.slug if parent is not None else TOP_LEVEL_LABEL
                )
            )
