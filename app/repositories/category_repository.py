from uuid import UUID

from sqlalchemy import ColumnElement, Select, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.business import Business
from app.models.category import Category, CategoryStatus
from app.models.plugin_category_binding import PluginCategoryBinding
from app.schemas.pagination import PaginationParams


def category_subtree_ids(root_id: UUID) -> Select[tuple[UUID]]:
    tree = select(Category.id).where(Category.id == root_id).cte("category_tree", recursive=True)
    tree = tree.union(select(Category.id).join(tree, Category.parent_id == tree.c.id))
    return select(tree.c.id)


def unavailable_category_tree_ids() -> Select[tuple[UUID]]:
    blocked = (
        select(Category.id)
        .where(or_(Category.is_active.is_(False), Category.status != CategoryStatus.PUBLISHED))
        .cte("blocked_categories", recursive=True)
    )
    blocked = blocked.union(select(Category.id).join(blocked, Category.parent_id == blocked.c.id))
    return select(blocked.c.id)


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, category_id: UUID) -> Category | None:
        return self._db.get(Category, category_id)

    def get_by_slug(self, slug: str) -> Category | None:
        return self._db.scalar(select(Category).where(Category.slug == slug))

    def get_chain(self, category_id: UUID) -> list[Category]:
        chain = (
            select(Category.id, Category.parent_id)
            .where(Category.id == category_id)
            .cte("category_chain", recursive=True)
        )
        chain = chain.union(
            select(Category.id, Category.parent_id).join(chain, Category.id == chain.c.parent_id)
        )
        return list(self._db.scalars(select(Category).where(Category.id.in_(select(chain.c.id)))))

    def list_by_parent(
        self, parent_id: UUID | None, params: PaginationParams, include_inactive: bool
    ) -> tuple[list[Category], int]:
        conditions: list[ColumnElement[bool]] = [
            Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id,
            Category.status == CategoryStatus.PUBLISHED,
        ]
        if not include_inactive:
            conditions.append(Category.is_active.is_(True))
        total = self._db.scalar(select(func.count()).select_from(Category).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Category)
            .where(*conditions)
            .order_by(Category.sort_order.asc(), Category.name.asc(), Category.id.asc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def search_active(self, query: str, limit: int) -> list[Category]:
        return list(
            self._db.scalars(
                select(Category)
                .where(
                    Category.name.ilike(f"%{query.strip()}%"),
                    Category.id.not_in(unavailable_category_tree_ids()),
                )
                .order_by(Category.name.asc(), Category.id.asc())
                .limit(limit)
            )
        )

    def list_pending(self, params: PaginationParams) -> tuple[list[Category], int]:
        conditions = [Category.status == CategoryStatus.PENDING]
        total = self._db.scalar(select(func.count()).select_from(Category).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Category)
            .options(joinedload(Category.parent), joinedload(Category.submitter))
            .where(*conditions)
            .order_by(Category.created_at.asc(), Category.id.asc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def exists_with_name(
        self, parent_id: UUID | None, name: str, exclude_id: UUID | None = None
    ) -> bool:
        conditions: list[ColumnElement[bool]] = [
            Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id,
            func.lower(Category.name) == name.strip().lower(),
            Category.status != CategoryStatus.REJECTED,
        ]
        if exclude_id is not None:
            conditions.append(Category.id != exclude_id)
        return bool(self._db.scalar(select(exists().where(*conditions))))

    def find_by_name(self, parent_id: UUID | None, name: str) -> Category | None:
        return self._db.scalar(
            select(Category).where(
                Category.parent_id.is_(None)
                if parent_id is None
                else Category.parent_id == parent_id,
                func.lower(Category.name) == name.strip().lower(),
                Category.status != CategoryStatus.REJECTED,
            )
        )

    def slug_exists(self, slug: str) -> bool:
        return bool(self._db.scalar(select(exists().where(Category.slug == slug))))

    def has_children(self, category_id: UUID) -> bool:
        return bool(self._db.scalar(select(exists().where(Category.parent_id == category_id))))

    def is_used_by_businesses(self, category_id: UUID) -> bool:
        return bool(self._db.scalar(select(exists().where(Business.category_id == category_id))))

    def is_bound_to_plugins(self, category_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(exists().where(PluginCategoryBinding.category_id == category_id))
            )
        )

    def stage(self, category: Category) -> Category:
        self._db.add(category)
        self._db.flush()
        return category

    def commit(self) -> None:
        self._db.commit()

    def add(self, category: Category) -> Category:
        self._db.add(category)
        self._db.commit()
        self._db.refresh(category)
        return category

    def save(self, category: Category) -> Category:
        self._db.commit()
        self._db.refresh(category)
        return category

    def delete(self, category: Category) -> None:
        self._db.delete(category)
        self._db.commit()
