from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import PostMessages
from app.core.storage import delete_media_file, save_post_image, save_post_video
from app.models.post_media import PostMedia, PostMediaType
from app.models.user import User
from app.repositories.post_media_repository import PostMediaRepository
from app.services.activity_log_service import ActivityLogService
from app.services.post_service import PostService


class PostMediaService:
    def __init__(self, db: Session) -> None:
        self._media = PostMediaRepository(db)
        self._posts = PostService(db)
        self._activity_logs = ActivityLogService(db)

    def list_for_post(self, post_id: UUID) -> list[PostMedia]:
        self._posts.get(post_id)
        return self._media.list_by_post(post_id)

    def attach(
        self,
        post_id: UUID,
        images: list[UploadFile],
        videos: list[UploadFile],
        video_thumbnails: list[UploadFile],
        upload_dir: str,
        actor: User,
    ) -> list[PostMedia]:
        if not images and not videos:
            return []
        post = self._posts.get(post_id)
        self._posts.ensure_can_modify(post, actor)
        if videos and len(video_thumbnails) != len(videos):
            raise BusinessRuleError(PostMessages.VIDEO_THUMBNAIL_REQUIRED)

        next_sort_order = len(self._media.list_by_post(post_id))
        created: list[PostMedia] = []

        for image in images:
            media = self._media.add(
                PostMedia(
                    post_id=post_id,
                    media_type=PostMediaType.IMAGE,
                    file_url=save_post_image(image, upload_dir),
                    sort_order=next_sort_order,
                )
            )
            next_sort_order += 1
            created.append(media)
            self._log_added(media, actor)

        for video, thumbnail in zip(videos, video_thumbnails, strict=True):
            media = self._media.add(
                PostMedia(
                    post_id=post_id,
                    media_type=PostMediaType.VIDEO,
                    file_url=save_post_video(video, upload_dir),
                    thumbnail_url=save_post_image(thumbnail, upload_dir),
                    sort_order=next_sort_order,
                )
            )
            next_sort_order += 1
            created.append(media)
            self._log_added(media, actor)

        return created

    def remove(self, post_id: UUID, media_id: UUID, upload_dir: str, actor: User) -> None:
        post = self._posts.get(post_id)
        self._posts.ensure_can_modify(post, actor)
        media = self._media.get_by_id(media_id)
        if media is None or media.post_id != post_id:
            raise NotFoundError(PostMessages.MEDIA_NOT_FOUND)
        self._media.delete(media)
        delete_media_file(media.file_url, upload_dir)
        if media.thumbnail_url is not None:
            delete_media_file(media.thumbnail_url, upload_dir)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_MEDIA_REMOVED,
            entity_type="post_media",
            entity_id=media.id,
            metadata={"post_id": str(post_id)},
        )

    def _log_added(self, media: PostMedia, actor: User) -> None:
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_MEDIA_ADDED,
            entity_type="post_media",
            entity_id=media.id,
            metadata={"post_id": str(media.post_id), "media_type": media.media_type.value},
        )
