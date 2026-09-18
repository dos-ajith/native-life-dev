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


def save_profile_image(file: UploadFile, upload_dir: str) -> str:
    extension = ALLOWED_PROFILE_IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise BusinessRuleError(StorageMessages.INVALID_IMAGE_TYPE)

    contents = file.file.read()
    if len(contents) > MAX_PROFILE_IMAGE_BYTES:
        raise BusinessRuleError(StorageMessages.IMAGE_TOO_LARGE)

    directory = Path(upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{extension}"
    (directory / filename).write_bytes(contents)

    return f"{MEDIA_URL_PREFIX}/{filename}"


def delete_profile_image(url: str, upload_dir: str) -> None:
    if not url.startswith(f"{MEDIA_URL_PREFIX}/"):
        return
    filename = Path(url).name
    Path(upload_dir, filename).unlink(missing_ok=True)
