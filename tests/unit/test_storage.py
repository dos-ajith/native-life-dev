import io
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import BusinessRuleError
from app.core.storage import (
    MAX_PROFILE_IMAGE_BYTES,
    delete_profile_image,
    save_profile_image,
)


def _upload_file(content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename="avatar.jpg",
        headers=Headers({"content-type": content_type}),
    )


def test_save_profile_image_rejects_unsupported_content_type(tmp_path: Path) -> None:
    with pytest.raises(BusinessRuleError):
        save_profile_image(_upload_file(b"data", "application/pdf"), str(tmp_path))


def test_save_profile_image_rejects_oversized_file(tmp_path: Path) -> None:
    oversized = b"a" * (MAX_PROFILE_IMAGE_BYTES + 1)
    with pytest.raises(BusinessRuleError):
        save_profile_image(_upload_file(oversized, "image/png"), str(tmp_path))


def test_save_profile_image_writes_file_and_returns_media_url(tmp_path: Path) -> None:
    url = save_profile_image(_upload_file(b"fake-bytes", "image/png"), str(tmp_path))

    assert url.startswith("/media/")
    assert url.endswith(".png")
    saved_file = tmp_path / url.removeprefix("/media/")
    assert saved_file.read_bytes() == b"fake-bytes"


def test_delete_profile_image_removes_file(tmp_path: Path) -> None:
    url = save_profile_image(_upload_file(b"fake-bytes", "image/jpeg"), str(tmp_path))
    saved_file = tmp_path / url.removeprefix("/media/")
    assert saved_file.exists()

    delete_profile_image(url, str(tmp_path))

    assert not saved_file.exists()


def test_delete_profile_image_ignores_external_url(tmp_path: Path) -> None:
    delete_profile_image("https://example.com/avatar.png", str(tmp_path))
