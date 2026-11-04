from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.post_repository import PostRepository, PostVisibilityScope
from app.schemas.pagination import PaginationParams
from app.schemas.update_feed import UpdateFeedItem
from app.services.native_area_resolver import NativeAreaResolver
from app.services.post_service import PostService
from app.services.user_settings_service import UserSettingsService

METERS_PER_KM = 1000
DISTANCE_KM_DECIMALS = 2


class UpdateFeedService:
    def __init__(self, db: Session) -> None:
        self._posts = PostRepository(db)
        self._areas = NativeAreaResolver(db)
        self._settings = UserSettingsService(db)
        self._post_details = PostService(db)

    def list_for(
        self, params: PaginationParams, viewer: User, temporary_village_id: UUID | None
    ) -> tuple[list[UpdateFeedItem], int]:
        areas = self._areas.required_areas(viewer, temporary_village_id)
        radius_meters = self._settings.nearby_radius_km(viewer) * METERS_PER_KM
        scope = PostVisibilityScope(
            owner_id=viewer.id, viewer_is_adult=viewer.is_adult is True, member_id=viewer.id
        )
        rows, total = self._posts.list_for_areas(
            params, scope, [area.point for area in areas], radius_meters
        )
        details = self._post_details.details_by_ids([post.id for post, _, _ in rows], viewer)
        items = [
            UpdateFeedItem.from_detail(
                details[post.id],
                areas[area_rank].source,
                round(meters / METERS_PER_KM, DISTANCE_KM_DECIMALS),
            )
            for post, area_rank, meters in rows
        ]
        return items, total
