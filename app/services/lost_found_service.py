from collections.abc import Sequence
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.core.messages import LostFoundMessages
from app.core.permissions import PermissionName
from app.core.timezone import app_now
from app.models.lost_found_item import LostFoundItem, LostFoundStatus
from app.models.user import User
from app.repositories.lost_found_image_repository import LostFoundImageRepository
from app.repositories.lost_found_repository import LostFoundRepository
from app.repositories.post_repository import AreaPoint
from app.repositories.spatial import point_from_coordinates
from app.repositories.user_repository import UserRepository
from app.schemas.lost_found import (
    LostFoundCreate,
    LostFoundListQuery,
    LostFoundRead,
    LostFoundResponseCreate,
    LostFoundUpdate,
)
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.category_service import CategoryService
from app.services.lost_found_image_service import LostFoundImageService, ensure_within_image_limit
from app.services.native_area_resolver import NativeAreaResolver
from app.services.notification_service import NotificationService
from app.services.user_settings_service import UserSettingsService

ENTITY_TYPE = "lost_found_item"
METERS_PER_KM = 1000
DISTANCE_KM_DECIMALS = 2
NEARBY_NOTIFICATION_RECIPIENT_LIMIT = 200


class LostFoundService:
    def __init__(self, db: Session) -> None:
        self._items = LostFoundRepository(db)
        self._images = LostFoundImageRepository(db)
        self._image_service = LostFoundImageService(db)
        self._users = UserRepository(db)
        self._categories = CategoryService(db)
        self._areas = NativeAreaResolver(db)
        self._settings = UserSettingsService(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)

    def create(
        self,
        payload: LostFoundCreate,
        files: list[UploadFile],
        upload_dir: str,
        actor: User,
    ) -> LostFoundRead:
        ensure_within_image_limit(len(files))
        self._categories.ensure_assignable(payload.category_id)
        item = self._items.add(
            LostFoundItem(
                user_id=actor.id,
                location=point_from_coordinates(payload.latitude, payload.longitude),
                **payload.model_dump(exclude={"latitude", "longitude"}),
            )
        )
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.LOST_FOUND_CREATED,
            entity_type=ENTITY_TYPE,
            entity_id=item.id,
            metadata={"kind": item.kind.value, "category_id": str(item.category_id)},
        )
        self._image_service.add(item, files, upload_dir, actor)
        self._notify_nearby_users(item, actor)
        return self.get_read(item.id, actor)

    def get_read(self, item_id: UUID, viewer: User) -> LostFoundRead:
        return self._to_reads([(self._get(item_id), None)], viewer)[0]

    def list_for(
        self, params: PaginationParams, viewer: User, query: LostFoundListQuery
    ) -> tuple[list[LostFoundRead], int]:
        areas, radius_km = self._list_scope(viewer, query)
        restrict_to_areas = query.latitude is not None or query.village_id is not None
        rows, total = self._items.list_reports(
            params,
            query.status,
            query.kind,
            query.category_id,
            query.q,
            areas,
            radius_km * METERS_PER_KM,
            restrict_to_areas,
        )
        distances = [
            None if meters is None else round(meters / METERS_PER_KM, DISTANCE_KM_DECIMALS)
            for _, _, meters in rows
        ]
        reads = self._to_reads(
            [(item, km) for (item, _, _), km in zip(rows, distances, strict=True)], viewer
        )
        return reads, total

    def update(self, item_id: UUID, payload: LostFoundUpdate, actor: User) -> LostFoundRead:
        item = self._get(item_id)
        self._ensure_can_modify(item, actor, PermissionName.LOST_FOUND_UPDATE_ANY)
        self._ensure_open(item)
        data = payload.model_dump(exclude={"latitude", "longitude"}, exclude_none=True)
        if "category_id" in data and data["category_id"] != item.category_id:
            self._categories.ensure_assignable(data["category_id"])
        for field, value in data.items():
            setattr(item, field, value)
        if payload.latitude is not None and payload.longitude is not None:
            item.location = point_from_coordinates(payload.latitude, payload.longitude)
        self._items.save(item)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.LOST_FOUND_UPDATED,
            entity_type=ENTITY_TYPE,
            entity_id=item.id,
            metadata={"updated_fields": list(data.keys())},
        )
        return self.get_read(item.id, actor)

    def resolve(self, item_id: UUID, actor: User) -> LostFoundRead:
        item = self._get(item_id)
        self._ensure_can_modify(item, actor, PermissionName.LOST_FOUND_UPDATE_ANY)
        if item.status == LostFoundStatus.RESOLVED:
            raise BusinessRuleError(LostFoundMessages.ALREADY_RESOLVED)
        item.status = LostFoundStatus.RESOLVED
        item.resolved_at = app_now()
        self._items.save(item)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.LOST_FOUND_RESOLVED,
            entity_type=ENTITY_TYPE,
            entity_id=item.id,
        )
        self._notifications.notify_lost_found_resolved(
            item.user_id, actor, item.id, item.title, item.kind.value
        )
        self._notifications.notify_lost_found_closed(
            actor, item.user_id, item.id, item.title, item.kind.value
        )
        return self.get_read(item.id, actor)

    def respond(self, item_id: UUID, payload: LostFoundResponseCreate, actor: User) -> None:
        item = self._get(item_id)
        self._ensure_open(item)
        if item.user_id == actor.id:
            raise BusinessRuleError(LostFoundMessages.CANNOT_RESPOND_OWN)
        if self._notifications.has_lost_found_response(item.user_id, actor, item.id):
            raise ConflictError(LostFoundMessages.ALREADY_RESPONDED)
        self._notifications.notify_lost_found_response(
            item.user_id, actor, item.id, item.title, item.kind.value, payload.note
        )
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.LOST_FOUND_RESPONDED,
            entity_type=ENTITY_TYPE,
            entity_id=item.id,
            metadata={"kind": item.kind.value},
        )

    def delete(self, item_id: UUID, actor: User) -> None:
        item = self._get(item_id)
        self._ensure_can_modify(item, actor, PermissionName.LOST_FOUND_DELETE_ANY)
        item.deleted_at = app_now()
        self._items.save(item)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.LOST_FOUND_DELETED,
            entity_type=ENTITY_TYPE,
            entity_id=item.id,
        )

    def add_images(
        self, item_id: UUID, files: list[UploadFile], upload_dir: str, actor: User
    ) -> LostFoundRead:
        item = self._get(item_id)
        self._ensure_can_modify(item, actor, PermissionName.LOST_FOUND_UPDATE_ANY)
        self._ensure_open(item)
        self._image_service.add(item, files, upload_dir, actor)
        return self.get_read(item.id, actor)

    def remove_image(self, item_id: UUID, image_id: UUID, upload_dir: str, actor: User) -> None:
        item = self._get(item_id)
        self._ensure_can_modify(item, actor, PermissionName.LOST_FOUND_UPDATE_ANY)
        self._ensure_open(item)
        self._image_service.remove(item, image_id, upload_dir, actor)

    def _notify_nearby_users(self, item: LostFoundItem, actor: User) -> None:
        recipient_ids = self._items.list_nearby_user_ids(
            item.latitude, item.longitude, actor.id, NEARBY_NOTIFICATION_RECIPIENT_LIMIT
        )
        for recipient_id in recipient_ids:
            self._notifications.notify_lost_found_nearby(
                recipient_id, actor, item.id, item.title, item.kind.value
            )

    def _get(self, item_id: UUID) -> LostFoundItem:
        item = self._items.get_by_id(item_id)
        if item is None:
            raise NotFoundError(LostFoundMessages.NOT_FOUND)
        return item

    @staticmethod
    def _ensure_can_modify(item: LostFoundItem, actor: User, override_permission: str) -> None:
        if item.user_id != actor.id and not has_permission(actor, override_permission):
            raise AuthorizationError(LostFoundMessages.NOT_OWNER)

    @staticmethod
    def _ensure_open(item: LostFoundItem) -> None:
        if item.status == LostFoundStatus.RESOLVED:
            raise BusinessRuleError(LostFoundMessages.RESOLVED_READ_ONLY)

    def _list_scope(self, viewer: User, query: LostFoundListQuery) -> tuple[list[AreaPoint], float]:
        default_radius_km = float(self._settings.nearby_radius_km(viewer))
        if query.latitude is not None and query.longitude is not None:
            return [
                AreaPoint(query.latitude, query.longitude)
            ], query.radius_km or default_radius_km
        if query.village_id is not None:
            return [self._areas.temporary_area(query.village_id).point], default_radius_km
        return [area.point for area in self._areas.native_areas(viewer)], default_radius_km

    def _to_reads(
        self, rows: Sequence[tuple[LostFoundItem, float | None]], viewer: User
    ) -> list[LostFoundRead]:
        if not rows:
            return []
        author_ids = list({item.user_id for item, _ in rows})
        authors = {user.id: user for user in self._users.get_by_ids_including_deleted(author_ids)}
        images = self._images.list_by_items([item.id for item, _ in rows])
        return [
            LostFoundRead.from_item(
                item, authors[item.user_id], images.get(item.id, []), viewer, distance_km
            )
            for item, distance_km in rows
        ]
