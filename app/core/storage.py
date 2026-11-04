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

ROLE_UPGRADE_DOCUMENTS_SUBDIR = "role_upgrade_documents"
BUSINESS_DOCUMENTS_SUBDIR = "business_documents"
AADHAAR_DOCUMENTS_SUBDIR = "aadhaar_documents"
DEAL_IMAGES_SUBDIR = "deal_images"
CONTENT_TYPE_ALIASES = {"image/jpg": "image/jpeg", "image/pjpeg": "image/jpeg"}
GENERIC_CONTENT_TYPES = frozenset({"", "application/octet-stream", "binary/octet-stream"})
FILE_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
)
WEBP_RIFF_MARKER = b"RIFF"
WEBP_FORMAT_MARKER = b"WEBP"
MAX_PRIVATE_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_PRIVATE_DOCUMENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
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


def save_business_image(file: UploadFile, upload_dir: str) -> str:
    return save_post_image(file, upload_dir)


def save_lost_found_image(file: UploadFile, upload_dir: str) -> str:
    return save_post_image(file, upload_dir)


def save_event_image(file: UploadFile, upload_dir: str) -> str:
    return save_post_image(file, upload_dir)


def save_popular_place_image(file: UploadFile, upload_dir: str) -> str:
    return save_post_image(file, upload_dir)


def save_native_place_image(file: UploadFile, upload_dir: str) -> str:
    return save_post_image(file, upload_dir)


def save_community_image(file: UploadFile, upload_dir: str) -> str:
    return save_post_image(file, upload_dir)


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


def _save_private_document(
    file: UploadFile, private_upload_dir: str, subdir: str
) -> tuple[str, str, int]:
    return _save_private_upload(
        file,
        private_upload_dir,
        subdir,
        ALLOWED_PRIVATE_DOCUMENT_TYPES,
        MAX_PRIVATE_DOCUMENT_BYTES,
        StorageMessages.INVALID_DOCUMENT_TYPE,
        StorageMessages.DOCUMENT_TOO_LARGE,
    )


def _save_private_upload(
    file: UploadFile,
    private_upload_dir: str,
    subdir: str,
    allowed_types: dict[str, str],
    max_bytes: int,
    invalid_type_message: str,
    too_large_message: str,
) -> tuple[str, str, int]:
    contents = file.file.read()
    content_type = _resolve_content_type(file.content_type, contents)
    extension = allowed_types.get(content_type)
    if extension is None:
        raise BusinessRuleError(invalid_type_message)
    if len(contents) > max_bytes:
        raise BusinessRuleError(too_large_message)

    directory = Path(private_upload_dir, subdir)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{extension}"
    storage_path = directory / filename
    storage_path.write_bytes(contents)

    return str(storage_path), content_type, len(contents)


def _resolve_content_type(declared: str | None, contents: bytes) -> str:
    normalized = (declared or "").split(";")[0].strip().lower()
    normalized = CONTENT_TYPE_ALIASES.get(normalized, normalized)
    if normalized in GENERIC_CONTENT_TYPES:
        return _detect_content_type(contents) or normalized
    return normalized


def _detect_content_type(contents: bytes) -> str | None:
    if contents[:4] == WEBP_RIFF_MARKER and contents[8:12] == WEBP_FORMAT_MARKER:
        return "image/webp"
    return next(
        (
            content_type
            for signature, content_type in FILE_SIGNATURES
            if contents.startswith(signature)
        ),
        None,
    )


def delete_private_document(storage_path: str) -> None:
    Path(storage_path).unlink(missing_ok=True)


def save_role_upgrade_document(file: UploadFile, private_upload_dir: str) -> tuple[str, str, int]:
    return _save_private_document(file, private_upload_dir, ROLE_UPGRADE_DOCUMENTS_SUBDIR)


def delete_role_upgrade_document(storage_path: str) -> None:
    delete_private_document(storage_path)


def save_business_document(file: UploadFile, private_upload_dir: str) -> tuple[str, str, int]:
    return _save_private_document(file, private_upload_dir, BUSINESS_DOCUMENTS_SUBDIR)


def save_aadhaar_document(file: UploadFile, private_upload_dir: str) -> tuple[str, str, int]:
    return _save_private_document(file, private_upload_dir, AADHAAR_DOCUMENTS_SUBDIR)


def save_deal_image(file: UploadFile, private_upload_dir: str) -> tuple[str, str, int]:
    return _save_private_upload(
        file,
        private_upload_dir,
        DEAL_IMAGES_SUBDIR,
        ALLOWED_POST_IMAGE_TYPES,
        MAX_POST_IMAGE_BYTES,
        StorageMessages.INVALID_IMAGE_TYPE,
        StorageMessages.IMAGE_TOO_LARGE,
    )
