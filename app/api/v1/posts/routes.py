from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import (
    ActivityRequestMetaDep,
    CurrentActiveUserDep,
    DbSessionDep,
    PaginationDep,
    SettingsDep,
)
from app.api.v1.posts.permissions import PostCreateDep, PostViewDep
from app.core.config import Settings
from app.core.messages import PostMessages
from app.core.openapi_tags import ApiTag
from app.models.post import Post, PostAudience, PostStatus, PostVisibility
from app.models.post_media import PostMedia
from app.models.tag import Tag
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.post import (
    NearbyPostDetailRead,
    NearbyPostPage,
    PostCreate,
    PostDetailRead,
    PostListQuery,
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

router = APIRouter(prefix="/posts", tags=[ApiTag.POSTS])


def with_media(post: Post, media: list[PostMedia], tags: list[Tag]) -> PostWithMediaRead:
    return PostWithMediaRead(
        post=PostRead.model_validate(post),
        media=[PostMediaRead.model_validate(item) for item in media],
        tags=[TagRead.model_validate(item) for item in tags],
    )


def update_post_with_media(
    db: Session,
    settings: Settings,
    post_id: UUID,
    payload: PostUpdate,
    actor: User,
    images: list[UploadFile],
    videos: list[UploadFile],
    video_thumbnails: list[UploadFile],
) -> SuccessResponse[PostWithMediaRead]:
    post_service = PostService(db)
    was_published = post_service.get(post_id).status == PostStatus.PUBLISHED
    post = post_service.update(post_id, payload, actor)
    media = PostMediaService(db).attach(
        post.id, images, videos, video_thumbnails, settings.upload_dir, actor
    )
    if payload.tags is not None:
        post_tags = TagService(db).set_post_tags(post.id, payload.tags, actor)
    else:
        post_tags = post_service.list_tags(post.id)
    post_service.announce_community_post(post, newly_published=not was_published)
    return SuccessResponse(message=PostMessages.UPDATED, data=with_media(post, media, post_tags))


@router.post(
    "", response_model=SuccessResponse[PostWithMediaRead], status_code=status.HTTP_201_CREATED
)
def create_post(
    db: DbSessionDep,
    current_user: PostCreateDep,
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
    PostService(db).announce_community_post(post, newly_published=True)
    return SuccessResponse(message=PostMessages.CREATED, data=with_media(post, media, post_tags))


@router.get("", response_model=SuccessResponse[Page[PostDetailRead] | NearbyPostPage])
def list_posts(
    db: DbSessionDep,
    viewer: PostViewDep,
    params: PaginationDep,
    nearby: Annotated[PostListQuery, Query()],
) -> SuccessResponse[Page[PostDetailRead] | NearbyPostPage]:
    service = PostService(db)
    latitude, longitude = nearby.latitude, nearby.longitude
    priority_radius_km = None
    if latitude is None or longitude is None:
        area = service.default_feed_area(viewer) if nearby.user_id is None else None
        if area is not None:
            latitude, longitude = area.latitude, area.longitude
            priority_radius_km = area.radius_km
    if latitude is None or longitude is None:
        items, total = service.list_with_details(params, viewer, nearby.user_id)
        return SuccessResponse(
            message=PostMessages.LIST_RETRIEVED,
            data=Page[PostDetailRead].create(items=items, total=total, params=params),
        )
    ranked, total = service.list_nearby_with_details(
        params,
        viewer,
        latitude,
        longitude,
        nearby.radius_km,
        user_id=nearby.user_id,
        priority_radius_km=priority_radius_km,
    )
    base = Page[NearbyPostDetailRead].create(
        items=[NearbyPostDetailRead.from_detail(detail, km) for detail, km in ranked],
        total=total,
        params=params,
    )
    return SuccessResponse(
        message=PostMessages.LIST_RETRIEVED,
        data=NearbyPostPage(
            items=base.items,
            total=base.total,
            page=base.page,
            page_size=base.page_size,
            pages=base.pages,
            radius_km=nearby.radius_km,
        ),
    )


@router.get("/{slug}", response_model=SuccessResponse[PostDetailRead])
def get_post(slug: str, db: DbSessionDep, viewer: PostViewDep) -> SuccessResponse[PostDetailRead]:
    detail = PostService(db).get_detail_by_slug(slug, viewer)
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
        db,
        settings,
        post_id,
        payload,
        current_user,
        images or [],
        videos or [],
        video_thumbnails or [],
    )


@router.delete("/{post_id}", response_model=SuccessResponse[None])
def delete_post(
    post_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    PostService(db).delete(post_id, current_user)
    return SuccessResponse(message=PostMessages.DELETED, data=None)


@router.get("/{post_id}/media", response_model=SuccessResponse[list[PostMediaRead]])
def list_post_media(
    post_id: UUID, db: DbSessionDep, viewer: PostViewDep
) -> SuccessResponse[list[PostMediaRead]]:
    media = PostMediaService(db).list_for_post(post_id, viewer)
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
