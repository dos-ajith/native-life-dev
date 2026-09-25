from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import CollectionMessages
from app.schemas.collection import CollectionCreate, CollectionRead, CollectionUpdate
from app.schemas.pagination import Page
from app.schemas.post import PostDetailRead
from app.schemas.response import SuccessResponse
from app.services.collection_service import CollectionService

me_router = APIRouter(prefix="/me/collections", tags=["collections"])


@me_router.post(
    "", response_model=SuccessResponse[CollectionRead], status_code=status.HTTP_201_CREATED
)
def create_collection(
    payload: CollectionCreate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CollectionRead]:
    collection = CollectionService(db).create(payload, current_user)
    return SuccessResponse(message=CollectionMessages.CREATED, data=collection)


@me_router.get("", response_model=SuccessResponse[Page[CollectionRead]])
def list_collections(
    db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[CollectionRead]]:
    items, total = CollectionService(db).list_collections(current_user, params)
    page = Page[CollectionRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=CollectionMessages.LIST_RETRIEVED, data=page)


@me_router.get("/{collection_id}", response_model=SuccessResponse[CollectionRead])
def get_collection(
    collection_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[CollectionRead]:
    collection = CollectionService(db).get(collection_id, current_user)
    return SuccessResponse(message=CollectionMessages.RETRIEVED, data=collection)


@me_router.patch("/{collection_id}", response_model=SuccessResponse[CollectionRead])
def update_collection(
    collection_id: UUID,
    payload: CollectionUpdate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[CollectionRead]:
    collection = CollectionService(db).update(collection_id, payload, current_user)
    return SuccessResponse(message=CollectionMessages.UPDATED, data=collection)


@me_router.delete("/{collection_id}", response_model=SuccessResponse[None])
def delete_collection(
    collection_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    CollectionService(db).delete(collection_id, current_user)
    return SuccessResponse(message=CollectionMessages.DELETED, data=None)


@me_router.get("/{collection_id}/posts", response_model=SuccessResponse[Page[PostDetailRead]])
def list_collection_posts(
    collection_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
) -> SuccessResponse[Page[PostDetailRead]]:
    items, total = CollectionService(db).list_collection_posts(collection_id, current_user, params)
    page = Page[PostDetailRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=CollectionMessages.POSTS_RETRIEVED, data=page)


@me_router.post(
    "/{collection_id}/posts/{post_id}",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_201_CREATED,
)
def add_post_to_collection(
    collection_id: UUID, post_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    CollectionService(db).add_post(collection_id, post_id, current_user)
    return SuccessResponse(message=CollectionMessages.POST_ADDED, data=None)


@me_router.delete("/{collection_id}/posts/{post_id}", response_model=SuccessResponse[None])
def remove_post_from_collection(
    collection_id: UUID, post_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    CollectionService(db).remove_post(collection_id, post_id, current_user)
    return SuccessResponse(message=CollectionMessages.POST_REMOVED, data=None)
