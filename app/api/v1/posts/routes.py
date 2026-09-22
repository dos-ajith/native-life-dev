from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import (
    ActivityRequestMetaDep,
    CurrentActiveUserDep,
    DbSessionDep,
    PaginationDep,
    SettingsDep,
)
from app.core.messages import PostMessages
from app.models.post import Post, PostStatus
from app.models.post_media import PostMedia
from app.models.tag import Tag
from app.schemas.pagination import Page
from app.schemas.post import (
    PostCreate,
    PostDetailRead,
    PostMediaRead,
    PostRead,
    PostUpdate,
    PostWithMediaRead,
)
from app.schemas.response import SuccessResponse
from app.schemas.tag import TagRead
from app.services.post_media_service import PostMediaService
from app.services.post_service import PostService
from app.services.tag_service import TagService

router = APIRouter(prefix="/posts", tags=["posts"])


def _with_media(post: Post, media: list[PostMedia], tags: list[Tag]) -> PostWithMediaRead:
    return PostWithMediaRead(
        post=PostRead.model_validate(post),
        media=[PostMediaRead.model_validate(item) for item in media],
        tags=[TagRead.model_validate(item) for item in tags],
    )


@router.post(
    "", response_model=SuccessResponse[PostWithMediaRead], status_code=status.HTTP_201_CREATED
)
def create_post(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    meta: ActivityRequestMetaDep,
    settings: SettingsDep,
    title: Annotated[str | None, Form()] = None,
    content: Annotated[str | None, Form()] = None,
    post_status: Annotated[PostStatus, Form(alias="status")] = PostStatus.DRAFT,
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
        title=title,
        content=content,
        status=post_status,
        scheduled_at=scheduled_at,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        tags=tags,
    )
    post = PostService(db).create(payload, current_user, meta.ip_address, meta.user_agent)
    media = PostMediaService(db).attach(
        post.id,
        images or [],
        videos or [],
        video_thumbnails or [],
        settings.upload_dir,
        current_user,
    )
    post_tags = (
        TagService(db).set_post_tags(post.id, payload.tags, current_user) if payload.tags else []
    )
    return SuccessResponse(message=PostMessages.CREATED, data=_with_media(post, media, post_tags))


@router.get("", response_model=SuccessResponse[Page[PostDetailRead]])
def list_posts(
    db: DbSessionDep, _: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[PostDetailRead]]:
    items, total = PostService(db).list_with_details(params)
    page = Page[PostDetailRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=PostMessages.LIST_RETRIEVED, data=page)


@router.get("/{slug}", response_model=SuccessResponse[PostDetailRead])
def get_post(
    slug: str, db: DbSessionDep, _: CurrentActiveUserDep
) -> SuccessResponse[PostDetailRead]:
    detail = PostService(db).get_detail_by_slug(slug)
    return SuccessResponse(message=PostMessages.RETRIEVED, data=detail)


@router.patch("/{post_id}", response_model=SuccessResponse[PostWithMediaRead])
def update_post(
    post_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    title: Annotated[str | None, Form()] = None,
    content: Annotated[str | None, Form()] = None,
    post_status: Annotated[PostStatus | None, Form(alias="status")] = None,
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
        scheduled_at=scheduled_at,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        tags=tags,
    )
    post = PostService(db).update(post_id, payload, current_user)
    media = PostMediaService(db).attach(
        post.id,
        images or [],
        videos or [],
        video_thumbnails or [],
        settings.upload_dir,
        current_user,
    )
    if payload.tags is not None:
        post_tags = TagService(db).set_post_tags(post.id, payload.tags, current_user)
    else:
        post_tags = PostService(db).list_tags(post.id)
    return SuccessResponse(message=PostMessages.UPDATED, data=_with_media(post, media, post_tags))


@router.delete("/{post_id}", response_model=SuccessResponse[None])
def delete_post(
    post_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    PostService(db).delete(post_id, current_user)
    return SuccessResponse(message=PostMessages.DELETED, data=None)


@router.get("/{post_id}/media", response_model=SuccessResponse[list[PostMediaRead]])
def list_post_media(
    post_id: UUID, db: DbSessionDep, _: CurrentActiveUserDep
) -> SuccessResponse[list[PostMediaRead]]:
    media = PostMediaService(db).list_for_post(post_id)
    return SuccessResponse(
        message=PostMessages.MEDIA_RETRIEVED,
        data=[PostMediaRead.model_validate(item) for item in media],
    )


@router.delete("/{post_id}/media/{media_id}", response_model=SuccessResponse[None])
def delete_post_media(
    post_id: UUID,
    media_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
) -> SuccessResponse[None]:
    PostMediaService(db).remove(post_id, media_id, settings.upload_dir, current_user)
    return SuccessResponse(message=PostMessages.MEDIA_REMOVED, data=None)
