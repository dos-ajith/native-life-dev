import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import BusinessRuleError
from app.core.messages import StorageMessages

MEDIA_URL_PREFIX = "/media"

MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_PROFILE_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_POST_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_POST_IMAGE_TYPES = ALLOWED_PROFILE_IMAGE_TYPES

MAX_POST_VIDEO_BYTES = 100 * 1024 * 1024
ALLOWED_POST_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}


def _save_upload(
    file: UploadFile,
    upload_dir: str,
    allowed_types: dict[str, str],
    max_bytes: int,
    invalid_type_message: str,
    too_large_message: str,
) -> str:
    extension = allowed_types.get(file.content_type or "")
    if extension is None:
        raise BusinessRuleError(invalid_type_message)

    contents = file.file.read()
    if len(contents) > max_bytes:
        raise BusinessRuleError(too_large_message)

    directory = Path(upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{extension}"
    (directory / filename).write_bytes(contents)

    return f"{MEDIA_URL_PREFIX}/{filename}"


def save_profile_image(file: UploadFile, upload_dir: str) -> str:
    return _save_upload(
        file,
        upload_dir,
        ALLOWED_PROFILE_IMAGE_TYPES,
        MAX_PROFILE_IMAGE_BYTES,
        StorageMessages.INVALID_IMAGE_TYPE,
        StorageMessages.IMAGE_TOO_LARGE,
    )


def save_post_image(file: UploadFile, upload_dir: str) -> str:
    return _save_upload(
        file,
        upload_dir,
        ALLOWED_POST_IMAGE_TYPES,
        MAX_POST_IMAGE_BYTES,
        StorageMessages.INVALID_IMAGE_TYPE,
        StorageMessages.IMAGE_TOO_LARGE,
    )


def save_post_video(file: UploadFile, upload_dir: str) -> str:
    return _save_upload(
        file,
        upload_dir,
        ALLOWED_POST_VIDEO_TYPES,
        MAX_POST_VIDEO_BYTES,
        StorageMessages.INVALID_VIDEO_TYPE,
        StorageMessages.VIDEO_TOO_LARGE,
    )


def delete_media_file(url: str, upload_dir: str) -> None:
    if not url.startswith(f"{MEDIA_URL_PREFIX}/"):
        return
    filename = Path(url).name
    Path(upload_dir, filename).unlink(missing_ok=True)
