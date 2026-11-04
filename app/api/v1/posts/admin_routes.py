from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import ActivityRequestMetaDep, DbSessionDep, PaginationDep, SettingsDep
from app.api.v1.posts.permissions import PostBlockDep, PostCreateAnyDep, PostViewAnyDep
from app.api.v1.posts.routes import update_post_with_media, with_media
from app.core.messages import PostMessages
from app.core.openapi_tags import ApiTag
from app.models.post import PostAudience, PostStatus, PostVisibility
from app.schemas.pagination import Page
from app.schemas.post import (
    AdminPostListQuery,
    PostBlock,
    PostCreate,
    PostDetailRead,
    PostRead,
    PostUpdate,
    PostWithMediaRead,
)
from app.schemas.response import SuccessResponse
from app.services.post_media_service import PostMediaService
from app.services.post_service import PostService
from app.services.tag_service import TagService

router = APIRouter(prefix="/admin/posts", tags=[ApiTag.ADMIN_POSTS])


@router.get("", response_model=SuccessResponse[Page[PostDetailRead]])
def list_posts_as_admin(
    db: DbSessionDep,
    admin: PostViewAnyDep,
    params: PaginationDep,
    filters: Annotated[AdminPostListQuery, Query()],
) -> SuccessResponse[Page[PostDetailRead]]:
    items, total = PostService(db).list_for_admin_with_details(
        params,
        admin,
        filters.status,
        filters.audience,
        filters.visibility,
        filters.user_id,
        filters.community_id,
        filters.q,
    )
    return SuccessResponse(
        message=PostMessages.ADMIN_LIST_RETRIEVED,
        data=Page[PostDetailRead].create(items=items, total=total, params=params),
    )


@router.get("/{post_id}", response_model=SuccessResponse[PostDetailRead])
def get_post_as_admin(
    post_id: UUID, db: DbSessionDep, admin: PostViewAnyDep
) -> SuccessResponse[PostDetailRead]:
    detail = PostService(db).get_detail_for_admin(post_id, admin)
    return SuccessResponse(message=PostMessages.RETRIEVED, data=detail)


@router.post(
    "", response_model=SuccessResponse[PostWithMediaRead], status_code=status.HTTP_201_CREATED
)
def create_post_as_admin(
    db: DbSessionDep,
    admin: PostCreateAnyDep,
    meta: ActivityRequestMetaDep,
    settings: SettingsDep,
    community_id: Annotated[UUID | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
    content: Annotated[str | None, Form()] = None,
    post_status: Annotated[PostStatus, Form(alias="status")] = PostStatus.DRAFT,
    audience: Annotated[PostAudience, Form()] = PostAudience.EVERYONE,
    visibility: Annotated[PostVisibility | None, Form()] = None,
    scheduled_at: Annotated[datetime | None, Form()] = None,
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    location_name: Annotated[str | None, Form()] = None,
    tags: Annotated[list[str] | None, Form()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
    videos: Annotated[list[UploadFile] | None, File()] = None,
    video_thumbnails: Annotated[list[UploadFile] | None, File()] = None,
) -> SuccessResponse[PostWithMediaRead]:
    payload = PostCreate(
        community_id=community_id,
        title=title,
        content=content,
        status=post_status,
        audience=audience,
        visibility=visibility,
        scheduled_at=scheduled_at,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        tags=tags,
    )
    post_service = PostService(db)
    post = post_service.create_as_admin(payload, admin, meta.ip_address, meta.user_agent)
    media = PostMediaService(db).attach(
        post.id,
        images or [],
        videos or [],
        video_thumbnails or [],
        settings.upload_dir,
        admin,
    )
    post_tags = TagService(db).set_post_tags(post.id, payload.tags, admin) if payload.tags else []
    post_service.announce_community_post(post, newly_published=True)
    return SuccessResponse(
        message=PostMessages.ADMIN_CREATED, data=with_media(post, media, post_tags)
    )


@router.post("/{post_id}/block", response_model=SuccessResponse[PostRead])
def block_post(
    post_id: UUID, payload: PostBlock, db: DbSessionDep, admin: PostBlockDep
) -> SuccessResponse[PostRead]:
    post = PostService(db).block(post_id, admin, payload.reason)
    return SuccessResponse(message=PostMessages.BLOCKED, data=PostRead.model_validate(post))


@router.post("/{post_id}/unblock", response_model=SuccessResponse[PostRead])
def unblock_post(post_id: UUID, db: DbSessionDep, admin: PostBlockDep) -> SuccessResponse[PostRead]:
    post = PostService(db).unblock(post_id, admin)
    return SuccessResponse(message=PostMessages.UNBLOCKED, data=PostRead.model_validate(post))


@router.patch("/{post_id}", response_model=SuccessResponse[PostWithMediaRead])
def update_own_post_as_admin(
    post_id: UUID,
    db: DbSessionDep,
    admin: PostCreateAnyDep,
    settings: SettingsDep,
    title: Annotated[str | None, Form()] = None,
    content: Annotated[str | None, Form()] = None,
    post_status: Annotated[PostStatus | None, Form(alias="status")] = None,
    audience: Annotated[PostAudience | None, Form()] = None,
    visibility: Annotated[PostVisibility | None, Form()] = None,
    scheduled_at: Annotated[datetime | None, Form()] = None,
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    location_name: Annotated[str | None, Form()] = None,
    tags: Annotated[list[str] | None, Form()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
    videos: Annotated[list[UploadFile] | None, File()] = None,
    video_thumbnails: Annotated[list[UploadFile] | None, File()] = None,
) -> SuccessResponse[PostWithMediaRead]:
    payload = PostUpdate(
        title=title,
        content=content,
        status=post_status,
        audience=audience,
        visibility=visibility,
        scheduled_at=scheduled_at,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        tags=tags,
    )
    return update_post_with_media(
        db, settings, post_id, payload, admin, images or [], videos or [], video_thumbnails or []
    )
