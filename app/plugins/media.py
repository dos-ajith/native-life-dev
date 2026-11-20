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
VIDEO_EXTENSION = ".mp4"
VIDEO_CONTENT_TYPE = "video/mp4"
MP4_BOX_MARKER = b"ftyp"
MP4_BOX_OFFSET = 4
MP4_BRAND_OFFSET = 8
MP4_HEADER_BYTES = 12
QUICKTIME_BRAND = b"qt  "
UPLOAD_CHUNK_BYTES = BYTES_PER_MB


@dataclass(frozen=True)
class StoredImage:
    url: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class StoredVideo:
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


def _is_mp4(header: bytes) -> bool:
    return (
        len(header) == MP4_HEADER_BYTES
        and header[MP4_BOX_OFFSET : MP4_BOX_OFFSET + len(MP4_BOX_MARKER)] == MP4_BOX_MARKER
        and header[MP4_BRAND_OFFSET:] != QUICKTIME_BRAND
    )


def _media_target(plugin_key: str, subdirectory: str, extension: str) -> tuple[Path, str]:
    relative = Path(
        PLUGIN_MEDIA_DIRECTORY, _ensure_safe_segment(plugin_key), _ensure_safe_segment(subdirectory)
    )
    directory = Path(get_settings().upload_dir) / relative
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{extension}"
    return directory / filename, f"{MEDIA_URL_PREFIX}/{relative.as_posix()}/{filename}"


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
    path, url = _media_target(plugin_key, subdirectory, IMAGE_EXTENSIONS[content_type])
    path.write_bytes(contents)
    return StoredImage(url=url, content_type=content_type, size_bytes=len(contents))


def _write_limited(file: UploadFile, header: bytes, path: Path, max_bytes: int) -> int:
    size = len(header)
    try:
        with path.open("wb") as target:
            target.write(header)
            while chunk := file.file.read(UPLOAD_CHUNK_BYTES):
                size += len(chunk)
                if size > max_bytes:
                    raise BusinessRuleError(
                        StorageMessages.PLUGIN_VIDEO_TOO_LARGE.format(
                            limit_mb=max_bytes // BYTES_PER_MB
                        )
                    )
                target.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return size


def save_plugin_video(
    file: UploadFile, plugin_key: str, subdirectory: str, max_bytes: int
) -> StoredVideo:
    header = file.file.read(MP4_HEADER_BYTES)
    if not _is_mp4(header):
        raise BusinessRuleError(StorageMessages.PLUGIN_INVALID_VIDEO_TYPE)
    path, url = _media_target(plugin_key, subdirectory, VIDEO_EXTENSION)
    size = _write_limited(file, header, path, max_bytes)
    return StoredVideo(url=url, content_type=VIDEO_CONTENT_TYPE, size_bytes=size)


def delete_plugin_video(url: str) -> None:
    delete_plugin_image(url)


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
