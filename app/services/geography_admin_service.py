from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.messages import GeographyMessages
from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.models.user import User
from app.repositories.gis_area_repository import (
    GisArea,
    GisAreaModel,
    GisAreaRepository,
    GisParentModel,
)
from app.repositories.post_repository import AreaPoint
from app.schemas.geography import GeographyAreaCreate
from app.services.activity_log_service import ActivityLogService

GENERATED_LGD_PREFIX = "MAN"
GENERATED_LGD_SUFFIX_LENGTH = 7


@dataclass(frozen=True)
class AreaLevel:
    label: str
    parent_label: str
    model: GisAreaModel
    parent_model: GisParentModel
    parent_not_found_message: str
    default_radius_m: int
    action: str
    entity_type: str


DISTRICT_LEVEL = AreaLevel(
    label="district",
    parent_label="state",
    model=GisDistrict,
    parent_model=GisState,
    parent_not_found_message=GeographyMessages.STATE_NOT_FOUND,
    default_radius_m=25_000,
    action=ActivityAction.GEOGRAPHY_DISTRICT_CREATED,
    entity_type="gis_district",
)
TALUK_LEVEL = AreaLevel(
    label="taluk",
    parent_label="district",
    model=GisTaluk,
    parent_model=GisDistrict,
    parent_not_found_message=GeographyMessages.DISTRICT_NOT_FOUND,
    default_radius_m=8_000,
    action=ActivityAction.GEOGRAPHY_TALUK_CREATED,
    entity_type="gis_taluk",
)
VILLAGE_LEVEL = AreaLevel(
    label="village",
    parent_label="taluk",
    model=GisVillage,
    parent_model=GisTaluk,
    parent_not_found_message=GeographyMessages.TALUK_NOT_FOUND,
    default_radius_m=1_500,
    action=ActivityAction.GEOGRAPHY_VILLAGE_CREATED,
    entity_type="gis_village",
)


def _generated_lgd_code() -> str:
    return f"{GENERATED_LGD_PREFIX}{uuid4().hex[:GENERATED_LGD_SUFFIX_LENGTH].upper()}"


class GeographyAdminService:
    def __init__(self, db: Session) -> None:
        self._areas = GisAreaRepository(db)
        self._activity_logs = ActivityLogService(db)

    def create_district(
        self, state_id: UUID, payload: GeographyAreaCreate, actor: User
    ) -> GisDistrict:
        district = GisDistrict(
            state_id=state_id,
            name=payload.name,
            lgd_code=payload.lgd_code or _generated_lgd_code(),
        )
        created = self._create(DISTRICT_LEVEL, district, state_id, payload, actor)
        assert isinstance(created, GisDistrict)
        return created

    def create_taluk(
        self, district_id: UUID, payload: GeographyAreaCreate, actor: User
    ) -> GisTaluk:
        taluk = GisTaluk(
            district_id=district_id,
            name=payload.name,
            lgd_code=payload.lgd_code or _generated_lgd_code(),
        )
        created = self._create(TALUK_LEVEL, taluk, district_id, payload, actor)
        assert isinstance(created, GisTaluk)
        return created

    def create_village(
        self, taluk_id: UUID, payload: GeographyAreaCreate, actor: User
    ) -> GisVillage:
        village = GisVillage(
            taluk_id=taluk_id,
            name=payload.name,
            lgd_code=payload.lgd_code or _generated_lgd_code(),
        )
        created = self._create(VILLAGE_LEVEL, village, taluk_id, payload, actor)
        assert isinstance(created, GisVillage)
        return created

    def _create(
        self,
        level: AreaLevel,
        area: GisArea,
        parent_id: UUID,
        payload: GeographyAreaCreate,
        actor: User,
    ) -> GisArea:
        point = AreaPoint(payload.latitude, payload.longitude)
        radius_m = payload.radius_m or level.default_radius_m
        self._ensure_placeable(level, area.lgd_code, parent_id, point)
        created = self._areas.add_clipped_circle(
            area, level.parent_model, parent_id, point, radius_m
        )
        self._activity_logs.log(
            actor=actor,
            action=level.action,
            entity_type=level.entity_type,
            entity_id=created.id,
            metadata={
                "parent_id": str(parent_id),
                "name": created.name,
                "lgd_code": created.lgd_code,
                "latitude": point.latitude,
                "longitude": point.longitude,
                "radius_m": radius_m,
            },
        )
        return created

    def _ensure_placeable(
        self, level: AreaLevel, lgd_code: str, parent_id: UUID, point: AreaPoint
    ) -> None:
        inside_parent = self._areas.parent_contains_point(level.parent_model, parent_id, point)
        if inside_parent is None:
            raise NotFoundError(level.parent_not_found_message)
        if not inside_parent:
            raise BusinessRuleError(
                GeographyMessages.POINT_OUTSIDE_PARENT.format(parent=level.parent_label)
            )
        existing_name = self._areas.find_name_containing_point(level.model, point)
        if existing_name is not None:
            raise ConflictError(
                GeographyMessages.AREA_ALREADY_COVERED.format(level=level.label, name=existing_name)
            )
        if self._areas.lgd_code_exists(level.model, lgd_code):
            raise ConflictError(GeographyMessages.LGD_CODE_TAKEN.format(code=lgd_code))
