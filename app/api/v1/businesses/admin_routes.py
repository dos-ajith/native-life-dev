from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.api.deps import ActivityRequestMetaDep, DbSessionDep, PaginationDep, SettingsDep
from app.api.v1.businesses.permissions import (
    BusinessCreateAnyDep,
    BusinessEscalateDep,
    BusinessReviewDep,
)
from app.core.messages import BusinessMessages
from app.core.openapi_tags import ApiTag
from app.schemas.business import BusinessCreate, BusinessCreatedRead, BusinessDocumentRead
from app.schemas.business_review import (
    BusinessCountsRead,
    BusinessDocumentReview,
    BusinessEscalate,
    BusinessReject,
    BusinessReviewDetailRead,
    BusinessReviewQuery,
    BusinessReviewRead,
)
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.business_attachment_storage import BusinessUploads
from app.services.business_verification_service import BusinessVerificationService

router = APIRouter(prefix="/admin/businesses", tags=[ApiTag.BUSINESS_VERIFICATION])

ReviewQueryDep = Annotated[BusinessReviewQuery, Depends()]


@router.get("", response_model=SuccessResponse[Page[BusinessReviewRead]])
def list_businesses_for_review(
    db: DbSessionDep, admin: BusinessReviewDep, params: PaginationDep, query: ReviewQueryDep
) -> SuccessResponse[Page[BusinessReviewRead]]:
    items, total = BusinessVerificationService(db).list_for_review(query, params, admin)
    page = Page[BusinessReviewRead].create(
        items=[BusinessReviewRead.from_business_for_review(item) for item in items],
        total=total,
        params=params,
    )
    return SuccessResponse(message=BusinessMessages.LIST_RETRIEVED, data=page)


@router.post(
    "", response_model=SuccessResponse[BusinessCreatedRead], status_code=status.HTTP_201_CREATED
)
def create_business_for_owner(
    db: DbSessionDep,
    settings: SettingsDep,
    admin: BusinessCreateAnyDep,
    meta: ActivityRequestMetaDep,
    owner_id: Annotated[UUID, Form()],
    name: Annotated[str, Form()],
    category_id: Annotated[UUID, Form()],
    description: Annotated[str | None, Form()] = None,
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
    documents: Annotated[list[UploadFile] | None, File()] = None,
    document_types: Annotated[list[str] | None, Form()] = None,
) -> SuccessResponse[BusinessCreatedRead]:
    payload = BusinessCreate(
        name=name,
        category_id=category_id,
        description=description,
        latitude=latitude,
        longitude=longitude,
        document_types=document_types or [],
    )
    uploads = BusinessUploads(
        images=images or [],
        documents=documents or [],
        upload_dir=settings.upload_dir,
        private_upload_dir=settings.private_upload_dir,
    )
    created = BusinessVerificationService(db).create_for_owner(
        payload, uploads, owner_id, admin, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(
        message=BusinessMessages.ADMIN_CREATED,
        data=BusinessCreatedRead.from_created(created.business, created.images, created.documents),
    )


@router.get("/export")
def export_businesses(
    db: DbSessionDep, admin: BusinessReviewDep, query: ReviewQueryDep
) -> Response:
    content = BusinessVerificationService(db).export_csv(query, admin)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="businesses.csv"'},
    )


@router.get("/counts", response_model=SuccessResponse[BusinessCountsRead])
def get_business_counts(
    db: DbSessionDep, admin: BusinessReviewDep
) -> SuccessResponse[BusinessCountsRead]:
    counts = BusinessVerificationService(db).counts(admin)
    return SuccessResponse(
        message=BusinessMessages.COUNTS_RETRIEVED, data=BusinessCountsRead.from_counts(counts)
    )


@router.get("/{business_id}", response_model=SuccessResponse[BusinessReviewDetailRead])
def get_business_for_review(
    business_id: UUID, db: DbSessionDep, admin: BusinessReviewDep
) -> SuccessResponse[BusinessReviewDetailRead]:
    result = BusinessVerificationService(db).get_for_review(business_id, admin)
    return SuccessResponse(
        message=BusinessMessages.RETRIEVED,
        data=BusinessReviewDetailRead.from_parts(result.business, result.images, result.documents),
    )


@router.post("/{business_id}/escalate", response_model=SuccessResponse[BusinessReviewRead])
def escalate_business(
    business_id: UUID, payload: BusinessEscalate, db: DbSessionDep, admin: BusinessEscalateDep
) -> SuccessResponse[BusinessReviewRead]:
    business = BusinessVerificationService(db).escalate(business_id, admin, payload.escalation_note)
    return SuccessResponse(
        message=BusinessMessages.ESCALATED,
        data=BusinessReviewRead.from_business_for_review(business),
    )


@router.post("/{business_id}/approve", response_model=SuccessResponse[BusinessReviewRead])
def approve_business(
    business_id: UUID, db: DbSessionDep, admin: BusinessReviewDep
) -> SuccessResponse[BusinessReviewRead]:
    business = BusinessVerificationService(db).approve(business_id, admin)
    return SuccessResponse(
        message=BusinessMessages.APPROVED,
        data=BusinessReviewRead.from_business_for_review(business),
    )


@router.post("/{business_id}/reject", response_model=SuccessResponse[BusinessReviewRead])
def reject_business(
    business_id: UUID, payload: BusinessReject, db: DbSessionDep, admin: BusinessReviewDep
) -> SuccessResponse[BusinessReviewRead]:
    business = BusinessVerificationService(db).reject(business_id, admin, payload.review_note)
    return SuccessResponse(
        message=BusinessMessages.REJECTED,
        data=BusinessReviewRead.from_business_for_review(business),
    )


@router.patch(
    "/{business_id}/documents/{document_id}",
    response_model=SuccessResponse[BusinessDocumentRead],
)
def review_business_document(
    business_id: UUID,
    document_id: UUID,
    payload: BusinessDocumentReview,
    db: DbSessionDep,
    admin: BusinessReviewDep,
) -> SuccessResponse[BusinessDocumentRead]:
    document = BusinessVerificationService(db).review_document(
        business_id, document_id, payload.status, admin
    )
    return SuccessResponse(
        message=BusinessMessages.DOCUMENT_REVIEWED,
        data=BusinessDocumentRead.model_validate(document),
    )


@router.get("/{business_id}/documents/{document_id}/file")
def download_business_document_for_review(
    business_id: UUID, document_id: UUID, db: DbSessionDep, admin: BusinessReviewDep
) -> FileResponse:
    document = BusinessVerificationService(db).get_document_for_review(
        business_id, document_id, admin
    )
    return FileResponse(
        path=document.storage_path,
        media_type=document.content_type,
        filename=document.file_name,
    )
