from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import NativePlaceMessages
from app.core.storage import delete_media_file, save_native_place_image
from app.models.gis_village import GisVillage
from app.models.user import User
from app.repositories.gis_village_repository import GisVillageRepository
from app.schemas.native_place import NativePlaceUpdate
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "native_place"


class NativePlaceAdminService:
    def __init__(self, db: Session) -> None:
        self._villages = GisVillageRepository(db)
        self._activity_logs = ActivityLogService(db)

    def update(
        self,
        village_id: UUID,
        payload: NativePlaceUpdate,
        image: UploadFile | None,
        upload_dir: str,
        actor: User,
    ) -> GisVillage:
        village = self._villages.get_by_id_without_geometry(village_id)
        if village is None:
            raise NotFoundError(NativePlaceMessages.VILLAGE_NOT_FOUND)
        if payload.tag_name is None and image is None:
            raise BusinessRuleError(NativePlaceMessages.NOTHING_TO_UPDATE)
        updated_fields: list[str] = []
        if payload.tag_name is not None:
            village.tag_name = payload.tag_name
            updated_fields.append("tag_name")
        previous_image_url = village.image_url
        new_image_url = save_native_place_image(image, upload_dir) if image is not None else None
        if new_image_url is not None:
            village.image_url = new_image_url
            updated_fields.append("image_url")
        try:
            self._villages.save(village)
        except Exception:
            if new_image_url is not None:
                delete_media_file(new_image_url, upload_dir)
            raise
        if new_image_url is not None and previous_image_url is not None:
            delete_media_file(previous_image_url, upload_dir)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.NATIVE_PLACE_UPDATED,
            entity_type=ENTITY_TYPE,
            entity_id=village.id,
            metadata={"updated_fields": updated_fields},
        )
        return village
