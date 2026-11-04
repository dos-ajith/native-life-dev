import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError
from app.core.messages import StorageMessages
from app.core.storage import (
    FILE_SIGNATURES,
    MEDIA_URL_PREFIX,
    WEBP_FORMAT_MARKER,
    WEBP_RIFF_MARKER,
)

PLUGIN_MEDIA_DIRECTORY = "plugins"
IMAGE_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
SAFE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
BYTES_PER_MB = 1024 * 1024
WEBP_FORMAT_OFFSET = 8


@dataclass(frozen=True)
class StoredImage:
    url: str
    content_type: str
    size_bytes: int


def _detect_image_type(contents: bytes) -> str | None:
    if (
        contents[: len(WEBP_RIFF_MARKER)] == WEBP_RIFF_MARKER
        and contents[WEBP_FORMAT_OFFSET : WEBP_FORMAT_OFFSET + len(WEBP_FORMAT_MARKER)]
        == WEBP_FORMAT_MARKER
    ):
        return "image/webp"
    detected = next(
        (kind for signature, kind in FILE_SIGNATURES if contents.startswith(signature)), None
    )
    return detected if detected in IMAGE_EXTENSIONS else None


def _ensure_safe_segment(value: str) -> str:
    if not SAFE_SEGMENT_PATTERN.match(value):
        raise ValueError(value)
    return value


def save_plugin_image(
    file: UploadFile, plugin_key: str, subdirectory: str, max_bytes: int
) -> StoredImage:
    contents = file.file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise BusinessRuleError(
            StorageMessages.PLUGIN_IMAGE_TOO_LARGE.format(limit_mb=max_bytes // BYTES_PER_MB)
        )
    content_type = _detect_image_type(contents)
    if content_type is None:
        raise BusinessRuleError(StorageMessages.INVALID_IMAGE_TYPE)
    relative = Path(
        PLUGIN_MEDIA_DIRECTORY, _ensure_safe_segment(plugin_key), _ensure_safe_segment(subdirectory)
    )
    directory = Path(get_settings().upload_dir) / relative
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{IMAGE_EXTENSIONS[content_type]}"
    (directory / filename).write_bytes(contents)
    return StoredImage(
        url=f"{MEDIA_URL_PREFIX}/{relative.as_posix()}/{filename}",
        content_type=content_type,
        size_bytes=len(contents),
    )


def delete_plugin_image(url: str) -> None:
    prefix = f"{MEDIA_URL_PREFIX}/{PLUGIN_MEDIA_DIRECTORY}/"
    if not url.startswith(prefix):
        return
    base = (Path(get_settings().upload_dir) / PLUGIN_MEDIA_DIRECTORY).resolve()
    target = (Path(get_settings().upload_dir) / url.removeprefix(f"{MEDIA_URL_PREFIX}/")).resolve()
    if target.is_relative_to(base):
        target.unlink(missing_ok=True)


def delete_plugin_media(plugin_key: str) -> None:
    directory = (
        Path(get_settings().upload_dir) / PLUGIN_MEDIA_DIRECTORY / _ensure_safe_segment(plugin_key)
    )
    shutil.rmtree(directory, ignore_errors=True)
