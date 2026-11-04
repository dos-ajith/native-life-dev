from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import ConflictError, NotFoundError
from app.core.messages import NativePlaceMessages, PopularPlaceMessages
from app.core.storage import delete_media_file, save_popular_place_image
from app.models.gis_district import GisDistrict
from app.models.popular_place import PopularPlace
from app.models.user import User
from app.models.user_native_place import NativePlaceSlot
from app.repositories.gis_district_repository import GisDistrictRepository
from app.repositories.gis_village_repository import GisVillageRepository
from app.repositories.popular_place_repository import PopularPlaceFilter, PopularPlaceRepository
from app.repositories.post_repository import AreaPoint
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.pagination import PaginationParams
from app.schemas.popular_place import (
    PopularPlaceCreate,
    PopularPlaceListQuery,
    PopularPlaceUpdate,
)
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "popular_place"


@dataclass(frozen=True)
class PopularPlacesForViewer:
    district: GisDistrict | None
    places: list[tuple[PopularPlace, float | None]]
    primary_village_id: UUID | None


class PopularPlaceService:
    def __init__(self, db: Session) -> None:
        self._popular_places = PopularPlaceRepository(db)
        self._villages = GisVillageRepository(db)
        self._districts = GisDistrictRepository(db)
        self._native_places = UserNativePlaceRepository(db)
        self._activity_logs = ActivityLogService(db)

    def list_for_viewer(
        self, viewer: User | None, query: PopularPlaceListQuery
    ) -> PopularPlacesForViewer:
        primary_village_id = self._primary_village_id(viewer)
        near = (
            AreaPoint(query.latitude, query.longitude)
            if query.latitude is not None and query.longitude is not None
            else None
        )
        district = self._resolve_district(query, near, primary_village_id)
        filter_district_id = (
            district.id
            if district is not None and (query.district_id is not None or query.is_unfiltered)
            else None
        )
        places = self._popular_places.list_active(
            PopularPlaceFilter(
                district_id=filter_district_id,
                query=query.q.strip() if query.q is not None else None,
                near=near,
                limit=query.limit,
            )
        )
        return PopularPlacesForViewer(district, places, primary_village_id)

    def list_all(
        self, district_id: UUID | None, params: PaginationParams
    ) -> tuple[list[PopularPlace], int]:
        return self._popular_places.list_all(district_id, params)

    def get(self, popular_place_id: UUID) -> PopularPlace:
        popular_place = self._popular_places.get_by_id(popular_place_id)
        if popular_place is None:
            raise NotFoundError(PopularPlaceMessages.NOT_FOUND)
        return popular_place

    def create(
        self, payload: PopularPlaceCreate, image: UploadFile, upload_dir: str, actor: User
    ) -> PopularPlace:
        self._ensure_village_available(payload.village_id)
        image_url = save_popular_place_image(image, upload_dir)
        try:
            created = self._popular_places.add(
                PopularPlace(
                    village_id=payload.village_id,
                    image_url=image_url,
                    sort_order=payload.sort_order,
                    is_active=payload.is_active,
                    created_by=actor.id,
                )
            )
        except Exception:
            delete_media_file(image_url, upload_dir)
            raise
        self._log(actor, ActivityAction.POPULAR_PLACE_CREATED, created.id, created.village_id)
        return self.get(created.id)

    def update(
        self,
        popular_place_id: UUID,
        payload: PopularPlaceUpdate,
        image: UploadFile | None,
        upload_dir: str,
        actor: User,
    ) -> PopularPlace:
        popular_place = self.get(popular_place_id)
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        new_village_id = changes.get("village_id")
        if new_village_id is not None and new_village_id != popular_place.village_id:
            self._ensure_village_available(new_village_id, excluding_id=popular_place.id)
        for field, value in changes.items():
            setattr(popular_place, field, value)
        updated_fields = list(changes)
        previous_image_url = popular_place.image_url
        new_image_url = save_popular_place_image(image, upload_dir) if image is not None else None
        if new_image_url is not None:
            popular_place.image_url = new_image_url
            updated_fields.append("image_url")
        try:
            self._popular_places.save(popular_place)
        except Exception:
            if new_image_url is not None:
                delete_media_file(new_image_url, upload_dir)
            raise
        if new_image_url is not None:
            delete_media_file(previous_image_url, upload_dir)
        self._log(
            actor,
            ActivityAction.POPULAR_PLACE_UPDATED,
            popular_place.id,
            popular_place.village_id,
            {"updated_fields": updated_fields},
        )
        return self.get(popular_place.id)

    def delete(self, popular_place_id: UUID, upload_dir: str, actor: User) -> None:
        popular_place = self.get(popular_place_id)
        image_url = popular_place.image_url
        village_id = popular_place.village_id
        self._popular_places.delete(popular_place)
        delete_media_file(image_url, upload_dir)
        self._log(actor, ActivityAction.POPULAR_PLACE_DELETED, popular_place_id, village_id)

    def _primary_village_id(self, viewer: User | None) -> UUID | None:
        if viewer is None:
            return None
        primary = self._native_places.get_by_slot(viewer.id, NativePlaceSlot.PRIMARY)
        return primary.village_id if primary is not None else None

    def _resolve_district(
        self,
        query: PopularPlaceListQuery,
        near: AreaPoint | None,
        primary_village_id: UUID | None,
    ) -> GisDistrict | None:
        if query.district_id is not None:
            district = self._districts.get_without_geometry(query.district_id)
            if district is None:
                raise NotFoundError(NativePlaceMessages.DISTRICT_NOT_FOUND)
            return district
        if near is not None:
            return self._district_or_none(
                self._villages.find_district_id_containing_point(near.latitude, near.longitude)
            )
        if query.is_unfiltered and primary_village_id is not None:
            return self._district_or_none(self._villages.get_district_id(primary_village_id))
        return None

    def _district_or_none(self, district_id: UUID | None) -> GisDistrict | None:
        if district_id is None:
            return None
        return self._districts.get_without_geometry(district_id)

    def _ensure_village_available(self, village_id: UUID, excluding_id: UUID | None = None) -> None:
        if self._villages.get_district_id(village_id) is None:
            raise NotFoundError(NativePlaceMessages.VILLAGE_NOT_FOUND)
        if self._popular_places.exists_for_village(village_id, excluding_id):
            raise ConflictError(PopularPlaceMessages.ALREADY_EXISTS)

    def _log(
        self,
        actor: User,
        action: str,
        popular_place_id: UUID,
        village_id: UUID,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=popular_place_id,
            metadata={"village_id": str(village_id), **(metadata or {})},
        )
