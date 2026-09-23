from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import DbSessionDep, SettingsDep, require_permission
from app.core.messages import GeographyMessages
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.geography import GeographyImportSummary
from app.schemas.response import SuccessResponse
from app.services.geography_import_service import GeographyImportService

router = APIRouter(prefix="/admin/geography", tags=["admin"])

GeographyImportDep = Annotated[User, Depends(require_permission(PermissionName.GEOGRAPHY_IMPORT))]


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
