from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import DbSessionDep, SettingsDep, require_permission
from app.core.messages import GeographyMessages
from app.core.openapi_tags import ApiTag
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.geography import (
    GeographyAreaCreate,
    GeographyImportSummary,
    GisDistrictRead,
    GisTalukRead,
    GisVillageRead,
)
from app.schemas.response import SuccessResponse
from app.services.geography_admin_service import GeographyAdminService
from app.services.geography_import_service import GeographyImportService

router = APIRouter(prefix="/admin/geography", tags=[ApiTag.TOOLS_GEOGRAPHY])

GeographyImportDep = Annotated[User, Depends(require_permission(PermissionName.GEOGRAPHY_IMPORT))]
GeographyManageDep = Annotated[User, Depends(require_permission(PermissionName.GEOGRAPHY_MANAGE))]


@router.post("/import", response_model=SuccessResponse[GeographyImportSummary])
def import_geography(
    db: DbSessionDep,
    admin: GeographyImportDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(...)],
) -> SuccessResponse[GeographyImportSummary]:
    max_upload_bytes = settings.gis_import_max_upload_mb * 1024 * 1024
    summary = GeographyImportService(db).import_zip(file, max_upload_bytes, admin)
    return SuccessResponse(message=GeographyMessages.IMPORTED, data=summary)


@router.post(
    "/states/{state_id}/districts",
    response_model=SuccessResponse[GisDistrictRead],
    status_code=status.HTTP_201_CREATED,
)
def create_district(
    state_id: UUID, payload: GeographyAreaCreate, db: DbSessionDep, admin: GeographyManageDep
) -> SuccessResponse[GisDistrictRead]:
    district = GeographyAdminService(db).create_district(state_id, payload, admin)
    return SuccessResponse(
        message=GeographyMessages.DISTRICT_CREATED, data=GisDistrictRead.model_validate(district)
    )


@router.post(
    "/districts/{district_id}/taluks",
    response_model=SuccessResponse[GisTalukRead],
    status_code=status.HTTP_201_CREATED,
)
def create_taluk(
    district_id: UUID, payload: GeographyAreaCreate, db: DbSessionDep, admin: GeographyManageDep
) -> SuccessResponse[GisTalukRead]:
    taluk = GeographyAdminService(db).create_taluk(district_id, payload, admin)
    return SuccessResponse(
        message=GeographyMessages.TALUK_CREATED, data=GisTalukRead.model_validate(taluk)
    )


@router.post(
    "/taluks/{taluk_id}/villages",
    response_model=SuccessResponse[GisVillageRead],
    status_code=status.HTTP_201_CREATED,
)
def create_village(
    taluk_id: UUID, payload: GeographyAreaCreate, db: DbSessionDep, admin: GeographyManageDep
) -> SuccessResponse[GisVillageRead]:
    village = GeographyAdminService(db).create_village(taluk_id, payload, admin)
    return SuccessResponse(
        message=GeographyMessages.VILLAGE_CREATED, data=GisVillageRead.model_validate(village)
    )
