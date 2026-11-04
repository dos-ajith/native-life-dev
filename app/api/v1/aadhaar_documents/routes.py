from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import AadhaarDocumentMessages
from app.core.openapi_tags import ApiTag
from app.schemas.aadhaar_document import AadhaarDocumentRead
from app.schemas.response import SuccessResponse
from app.services.aadhaar_document_service import AadhaarDocumentService

router = APIRouter(prefix="/users/me/aadhaar-document", tags=[ApiTag.AADHAAR_DOCUMENT])


@router.put("", response_model=SuccessResponse[AadhaarDocumentRead])
def upload_my_aadhaar_document(
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> SuccessResponse[AadhaarDocumentRead]:
    documents = AadhaarDocumentService(db).upload(
        current_user, files or [], settings.private_upload_dir
    )
    return SuccessResponse(
        message=AadhaarDocumentMessages.UPLOADED,
        data=AadhaarDocumentRead.from_documents(documents),
    )


@router.get("", response_model=SuccessResponse[AadhaarDocumentRead])
def get_my_aadhaar_document(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[AadhaarDocumentRead]:
    documents = AadhaarDocumentService(db).list_files(current_user)
    return SuccessResponse(
        message=AadhaarDocumentMessages.RETRIEVED,
        data=AadhaarDocumentRead.from_documents(documents),
    )


@router.get("/files/{file_id}")
def download_my_aadhaar_file(
    file_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> FileResponse:
    document = AadhaarDocumentService(db).get_file(current_user, file_id)
    return FileResponse(
        path=document.storage_path,
        media_type=document.content_type,
        filename=document.file_name,
    )
