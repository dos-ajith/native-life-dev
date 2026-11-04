from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import UserAddressMessages
from app.core.openapi_tags import ApiTag
from app.schemas.response import SuccessResponse
from app.schemas.user_address import (
    AddressMapCenterRead,
    UserAddressCreate,
    UserAddressRead,
    UserAddressUpdate,
)
from app.services.user_address_service import UserAddressService

router = APIRouter(prefix="/users/me/addresses", tags=[ApiTag.USER_ADDRESSES])


@router.get("", response_model=SuccessResponse[list[UserAddressRead]])
def list_my_addresses(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[list[UserAddressRead]]:
    addresses = UserAddressService(db).list_for(current_user)
    return SuccessResponse(
        message=UserAddressMessages.LIST_RETRIEVED,
        data=[UserAddressRead.from_address(address) for address in addresses],
    )


@router.get("/map-center", response_model=SuccessResponse[AddressMapCenterRead])
def get_address_map_center(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[AddressMapCenterRead]:
    center = UserAddressService(db).map_center(current_user)
    return SuccessResponse(
        message=UserAddressMessages.MAP_CENTER_RETRIEVED,
        data=AddressMapCenterRead.from_center(center),
    )


@router.post(
    "", response_model=SuccessResponse[UserAddressRead], status_code=status.HTTP_201_CREATED
)
def create_my_address(
    payload: UserAddressCreate, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[UserAddressRead]:
    address = UserAddressService(db).create(payload, current_user)
    return SuccessResponse(
        message=UserAddressMessages.CREATED, data=UserAddressRead.from_address(address)
    )


@router.patch("/{address_id}", response_model=SuccessResponse[UserAddressRead])
def update_my_address(
    address_id: UUID,
    payload: UserAddressUpdate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[UserAddressRead]:
    address = UserAddressService(db).update(address_id, payload, current_user)
    return SuccessResponse(
        message=UserAddressMessages.UPDATED, data=UserAddressRead.from_address(address)
    )


@router.put("/{address_id}/default", response_model=SuccessResponse[UserAddressRead])
def set_my_default_address(
    address_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[UserAddressRead]:
    address = UserAddressService(db).set_default(address_id, current_user)
    return SuccessResponse(
        message=UserAddressMessages.DEFAULT_SET, data=UserAddressRead.from_address(address)
    )


@router.delete("/{address_id}", response_model=SuccessResponse[None])
def delete_my_address(
    address_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    UserAddressService(db).delete(address_id, current_user)
    return SuccessResponse(message=UserAddressMessages.DELETED, data=None)
