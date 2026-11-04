from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep, SettingsDep
from app.api.v1.deals.permissions import DealCreateDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.deal import (
    DealCreate,
    DealListQuery,
    DealRead,
    DealSubmissionRead,
    DealUpdate,
    parse_deal_items,
)
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.deal_service import DealService
from app.services.deal_submission_service import DealSubmissionService

router = APIRouter(prefix="/deals", tags=[ApiTag.DEALS])
me_router = APIRouter(prefix="/me/deals", tags=[ApiTag.DEALS])


@router.post("", response_model=SuccessResponse[DealRead], status_code=status.HTTP_201_CREATED)
def create_deal(
    db: DbSessionDep,
    settings: SettingsDep,
    registry: PluginRegistryDep,
    current_user: DealCreateDep,
    name: Annotated[str, Form()],
    category_id: Annotated[UUID, Form()],
    starts_at: Annotated[datetime, Form()],
    valid_until: Annotated[datetime, Form()],
    items: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    business_id: Annotated[UUID | None, Form()] = None,
    min_joiners: Annotated[int | None, Form()] = None,
    pickup_location: Annotated[str | None, Form()] = None,
    delivery_details: Annotated[str | None, Form()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> SuccessResponse[DealRead]:
    payload = DealCreate(
        name=name,
        category_id=category_id,
        description=description,
        business_id=business_id,
        min_joiners=min_joiners,
        starts_at=starts_at,
        valid_until=valid_until,
        pickup_location=pickup_location,
        delivery_details=delivery_details,
        items=parse_deal_items(items),
    )
    deal = DealService(db, registry).create(
        payload, images or [], settings.private_upload_dir, current_user
    )
    return SuccessResponse(message=DealMessages.CREATED, data=deal)


@router.get("/{deal_id}", response_model=SuccessResponse[DealRead])
def get_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealService(db).get_read(deal_id, current_user)
    return SuccessResponse(message=DealMessages.RETRIEVED, data=deal)


@router.patch("/{deal_id}", response_model=SuccessResponse[DealRead])
def update_deal(
    deal_id: UUID,
    payload: DealUpdate,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[DealRead]:
    deal = DealService(db, registry).update(deal_id, payload, current_user)
    return SuccessResponse(message=DealMessages.UPDATED, data=deal)


@router.delete("/{deal_id}", response_model=SuccessResponse[None])
def delete_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    DealService(db).delete(deal_id, current_user)
    return SuccessResponse(message=DealMessages.DELETED, data=None)


@router.post("/{deal_id}/submit", response_model=SuccessResponse[DealSubmissionRead])
def submit_deal(
    deal_id: UUID, db: DbSessionDep, registry: PluginRegistryDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealSubmissionRead]:
    result = DealSubmissionService(db, registry=registry).submit(deal_id, current_user)
    return SuccessResponse(
        message=DealMessages.SUBMITTED,
        data=DealSubmissionRead(deal=result.deal, invited_count=result.invited_count),
    )


@router.post("/{deal_id}/invitations/refresh", response_model=SuccessResponse[DealSubmissionRead])
def refresh_deal_invitations(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealSubmissionRead]:
    result = DealSubmissionService(db).refresh_invitations(deal_id, current_user)
    return SuccessResponse(
        message=DealMessages.INVITATIONS_REFRESHED,
        data=DealSubmissionRead(deal=result.deal, invited_count=result.invited_count),
    )


@router.post("/{deal_id}/cancel", response_model=SuccessResponse[DealRead])
def cancel_deal(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealService(db).cancel(deal_id, current_user)
    return SuccessResponse(message=DealMessages.CANCELLED, data=deal)


@me_router.get("", response_model=SuccessResponse[Page[DealRead]])
def list_my_deals(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    query: Annotated[DealListQuery, Query()],
) -> SuccessResponse[Page[DealRead]]:
    deals, total = DealService(db).list_mine(current_user, query.status, params)
    return SuccessResponse(
        message=DealMessages.LIST_RETRIEVED,
        data=Page[DealRead].create(items=deals, total=total, params=params),
    )
