from collections.abc import Sequence

from fastapi import UploadFile

from app.core.exceptions import BusinessRuleError
from app.core.messages import DealMessages
from app.core.storage import delete_private_document, save_deal_image
from app.models.deal_image import DealImage
from app.schemas.deal import MAX_DEAL_IMAGES


def store_deal_images(files: Sequence[UploadFile], private_upload_dir: str) -> list[DealImage]:
    if len(files) > MAX_DEAL_IMAGES:
        raise BusinessRuleError(DealMessages.TOO_MANY_IMAGES.format(limit=MAX_DEAL_IMAGES))
    images: list[DealImage] = []
    try:
        for position, file in enumerate(files):
            storage_path, content_type, size_bytes = save_deal_image(file, private_upload_dir)
            images.append(
                DealImage(
                    storage_path=storage_path,
                    content_type=content_type,
                    file_size_bytes=size_bytes,
                    is_thumbnail=position == 0,
                    sort_order=position,
                )
            )
    except Exception:
        discard_deal_images(images)
        raise
    return images


def discard_deal_images(images: Sequence[DealImage]) -> None:
    for image in images:
        delete_private_document(image.storage_path)
