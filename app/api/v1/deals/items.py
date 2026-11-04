from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.deal import DealItemCreate, DealItemUpdate, DealRead
from app.schemas.response import SuccessResponse
from app.services.deal_item_service import DealItemService

router = APIRouter(prefix="/deals/{deal_id}/items", tags=[ApiTag.DEAL_ITEMS])


@router.post("", response_model=SuccessResponse[DealRead], status_code=status.HTTP_201_CREATED)
def add_deal_item(
    deal_id: UUID,
    payload: DealItemCreate,
    db: DbSessionDep,
    registry: PluginRegistryDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[DealRead]:
    deal = DealItemService(db, registry).add(deal_id, payload, current_user)
    return SuccessResponse(message=DealMessages.ITEM_ADDED, data=deal)


@router.patch("/{item_id}", response_model=SuccessResponse[DealRead])
def update_deal_item(
    deal_id: UUID,
    item_id: UUID,
    payload: DealItemUpdate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[DealRead]:
    deal = DealItemService(db).update(deal_id, item_id, payload, current_user)
    return SuccessResponse(message=DealMessages.ITEM_UPDATED, data=deal)


@router.delete("/{item_id}", response_model=SuccessResponse[DealRead])
def delete_deal_item(
    deal_id: UUID, item_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealItemService(db).remove(deal_id, item_id, current_user)
    return SuccessResponse(message=DealMessages.ITEM_DELETED, data=deal)
