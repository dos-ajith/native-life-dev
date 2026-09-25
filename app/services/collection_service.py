from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import CollectionMessages
from app.models.collection import Collection
from app.models.user import User
from app.repositories.collection_post_repository import CollectionPostRepository
from app.repositories.collection_repository import CollectionRepository
from app.repositories.saved_post_repository import SavedPostRepository
from app.schemas.collection import CollectionCreate, CollectionRead, CollectionUpdate
from app.schemas.pagination import PaginationParams
from app.schemas.post import PostDetailRead
from app.services.activity_log_service import ActivityLogService
from app.services.post_service import PostService


class CollectionService:
    def __init__(self, db: Session) -> None:
        self._collections = CollectionRepository(db)
        self._collection_posts = CollectionPostRepository(db)
        self._saved_posts = SavedPostRepository(db)
        self._posts = PostService(db)
        self._activity_logs = ActivityLogService(db)

    def _get_owned(self, collection_id: UUID, actor: User) -> Collection:
        collection = self._collections.get_by_id(collection_id)
        if collection is None or collection.user_id != actor.id:
            raise NotFoundError(CollectionMessages.NOT_FOUND)
        return collection

    def _to_read(self, collection: Collection) -> CollectionRead:
        post_count = self._collection_posts.count_by_collection(collection.id)
        return CollectionRead.from_collection(collection, post_count)

    def create(self, payload: CollectionCreate, actor: User) -> CollectionRead:
        collection = self._collections.add(
            Collection(user_id=actor.id, name=payload.name, description=payload.description)
        )
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COLLECTION_CREATED,
            entity_type="collection",
            entity_id=collection.id,
        )
        return self._to_read(collection)

    def get(self, collection_id: UUID, actor: User) -> CollectionRead:
        return self._to_read(self._get_owned(collection_id, actor))

    def list_collections(
        self, actor: User, params: PaginationParams
    ) -> tuple[list[CollectionRead], int]:
        collections, total = self._collections.list_by_user(actor.id, params)
        if not collections:
            return [], total
        counts = self._collection_posts.count_by_collections([c.id for c in collections])
        items = [
            CollectionRead.from_collection(collection, counts.get(collection.id, 0))
            for collection in collections
        ]
        return items, total

    def update(self, collection_id: UUID, payload: CollectionUpdate, actor: User) -> CollectionRead:
        collection = self._get_owned(collection_id, actor)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(collection, field, value)
        collection = self._collections.save(collection)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COLLECTION_UPDATED,
            entity_type="collection",
            entity_id=collection.id,
            metadata={"updated_fields": list(data.keys())},
        )
        return self._to_read(collection)

    def delete(self, collection_id: UUID, actor: User) -> None:
        collection = self._get_owned(collection_id, actor)
        self._collections.delete(collection)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COLLECTION_DELETED,
            entity_type="collection",
            entity_id=collection.id,
        )

    def add_post(self, collection_id: UUID, post_id: UUID, actor: User) -> None:
        collection = self._get_owned(collection_id, actor)
        post = self._posts.get_visible(post_id, actor)
        saved_post = self._saved_posts.get_by_user_and_post(actor.id, post.id)
        if saved_post is None:
            raise BusinessRuleError(CollectionMessages.POST_NOT_SAVED)
        if not self._collection_posts.create(collection.id, saved_post.id):
            raise BusinessRuleError(CollectionMessages.POST_ALREADY_IN_COLLECTION)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COLLECTION_POST_ADDED,
            entity_type="collection",
            entity_id=collection.id,
            metadata={"post_id": str(post.id)},
        )

    def remove_post(self, collection_id: UUID, post_id: UUID, actor: User) -> None:
        collection = self._get_owned(collection_id, actor)
        saved_post = self._saved_posts.get_by_user_and_post(actor.id, post_id)
        removed = saved_post is not None and self._collection_posts.delete(
            collection.id, saved_post.id
        )
        if not removed:
            raise NotFoundError(CollectionMessages.POST_NOT_IN_COLLECTION)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COLLECTION_POST_REMOVED,
            entity_type="collection",
            entity_id=collection.id,
            metadata={"post_id": str(post_id)},
        )

    def list_collection_posts(
        self, collection_id: UUID, actor: User, params: PaginationParams
    ) -> tuple[list[PostDetailRead], int]:
        collection = self._get_owned(collection_id, actor)
        return self._posts.list_by_collection_with_details(collection.id, params, actor)
