from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import BusinessMessages
from app.core.openapi_tags import ApiTag
from app.schemas.business import BusinessDocumentRead, DocumentType
from app.schemas.response import SuccessResponse
from app.services.business_document_service import BusinessDocumentService

router = APIRouter(prefix="/businesses/{business_id}/documents", tags=[ApiTag.BUSINESS_DOCUMENTS])


@router.post(
    "",
    response_model=SuccessResponse[BusinessDocumentRead],
    status_code=status.HTTP_201_CREATED,
)
def add_business_document(
    business_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
    document_type: Annotated[DocumentType, Form()],
    file: Annotated[UploadFile, File()],
) -> SuccessResponse[BusinessDocumentRead]:
    document = BusinessDocumentService(db, settings).add(
        business_id, document_type, file, current_user
    )
    return SuccessResponse(
        message=BusinessMessages.DOCUMENT_ADDED,
        data=BusinessDocumentRead.model_validate(document),
    )


@router.get("", response_model=SuccessResponse[list[BusinessDocumentRead]])
def list_business_documents(
    business_id: UUID, db: DbSessionDep, settings: SettingsDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[list[BusinessDocumentRead]]:
    documents = BusinessDocumentService(db, settings).list_for_business(business_id, current_user)
    return SuccessResponse(
        message=BusinessMessages.DOCUMENTS_RETRIEVED,
        data=[BusinessDocumentRead.model_validate(document) for document in documents],
    )


@router.get("/{document_id}")
def download_business_document(
    business_id: UUID,
    document_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
) -> FileResponse:
    document = BusinessDocumentService(db, settings).get_for_download(
        business_id, document_id, current_user
    )
    return FileResponse(
        path=document.storage_path,
        media_type=document.content_type,
        filename=document.file_name,
    )


@router.delete("/{document_id}", response_model=SuccessResponse[None])
def delete_business_document(
    business_id: UUID,
    document_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[None]:
    BusinessDocumentService(db, settings).delete(business_id, document_id, current_user)
    return SuccessResponse(message=BusinessMessages.DOCUMENT_DELETED, data=None)
