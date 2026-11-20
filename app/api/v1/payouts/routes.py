from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.api.deps import (
    CurrentActiveUserDep,
    DbSessionDep,
    PaginationDep,
    PaymentGatewayDep,
    SettingsDep,
    require_permission,
)
from app.core.messages import DuesMessages, PayoutAccountMessages, PayoutMessages
from app.core.openapi_tags import ApiTag
from app.core.payouts import PayoutGateway, get_payout_gateway
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.payout import (
    DuesOwedRead,
    DuesPaymentRead,
    DuesSummaryRead,
    PayoutAccountRead,
    PayoutAccountWrite,
    PayoutBulkCreate,
    PayoutCreate,
    PayoutDetailRead,
    PayoutDueQuery,
    PayoutDueRead,
    PayoutListQuery,
    PayoutMarkPaid,
    PayoutRead,
)
from app.schemas.response import SuccessResponse
from app.services.dues_service import DuesService
from app.services.payout_account_service import PayoutAccountService
from app.services.payout_service import PayoutService


def get_payout_gateway_dependency(settings: SettingsDep) -> PayoutGateway | None:
    return get_payout_gateway(settings)


async def read_raw_body(request: Request) -> bytes:
    return await request.body()


PayoutGatewayDep = Annotated[PayoutGateway | None, Depends(get_payout_gateway_dependency)]
PayoutManagerDep = Annotated[User, Depends(require_permission(PermissionName.PAYOUT_MANAGE))]
RawBodyDep = Annotated[bytes, Depends(read_raw_body)]

me_router = APIRouter(prefix="/me", tags=[ApiTag.PAYOUTS])
dues_router = APIRouter(prefix="/me", tags=[ApiTag.COD_DUES])
admin_router = APIRouter(prefix="/admin/payouts", tags=[ApiTag.ADMIN_PAYOUTS])
admin_dues_router = APIRouter(prefix="/admin/dues", tags=[ApiTag.ADMIN_COD_DUES])
webhook_router = APIRouter(prefix="/payments/razorpayx", tags=[ApiTag.PAYMENTS])


@me_router.get("/payout-account", response_model=SuccessResponse[PayoutAccountRead])
def get_my_payout_account(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[PayoutAccountRead]:
    account = PayoutAccountService(db).get_mine(current_user)
    return SuccessResponse(message=PayoutAccountMessages.RETRIEVED, data=account)


@me_router.put("/payout-account", response_model=SuccessResponse[PayoutAccountRead])
def save_my_payout_account(
    payload: PayoutAccountWrite, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[PayoutAccountRead]:
    account = PayoutAccountService(db).save_mine(payload, current_user)
    return SuccessResponse(message=PayoutAccountMessages.SAVED, data=account)


@me_router.get(
    "/businesses/{business_id}/payout-account", response_model=SuccessResponse[PayoutAccountRead]
)
def get_business_payout_account(
    business_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[PayoutAccountRead]:
    account = PayoutAccountService(db).get_for_business(business_id, current_user)
    return SuccessResponse(message=PayoutAccountMessages.RETRIEVED, data=account)


@me_router.put(
    "/businesses/{business_id}/payout-account", response_model=SuccessResponse[PayoutAccountRead]
)
def save_business_payout_account(
    business_id: UUID,
    payload: PayoutAccountWrite,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[PayoutAccountRead]:
    account = PayoutAccountService(db).save_for_business(business_id, payload, current_user)
    return SuccessResponse(message=PayoutAccountMessages.SAVED, data=account)


@me_router.get("/payouts", response_model=SuccessResponse[Page[PayoutRead]])
def list_my_payouts(
    db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[PayoutRead]]:
    items, total = PayoutService(db).list_mine(current_user, params)
    return SuccessResponse(
        message=PayoutMessages.LIST_RETRIEVED,
        data=Page[PayoutRead].create(items=items, total=total, params=params),
    )


@me_router.get(
    "/businesses/{business_id}/payouts", response_model=SuccessResponse[Page[PayoutRead]]
)
def list_business_payouts(
    business_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[PayoutRead]]:
    items, total = PayoutService(db).list_for_business(business_id, current_user, params)
    return SuccessResponse(
        message=PayoutMessages.LIST_RETRIEVED,
        data=Page[PayoutRead].create(items=items, total=total, params=params),
    )


@dues_router.get("/dues", response_model=SuccessResponse[DuesSummaryRead])
def my_dues(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DuesSummaryRead]:
    return SuccessResponse(
        message=DuesMessages.RETRIEVED, data=DuesService(db).summary_mine(current_user)
    )


@dues_router.post("/dues/pay", response_model=SuccessResponse[DuesPaymentRead])
def pay_my_dues(
    db: DbSessionDep, current_user: CurrentActiveUserDep, gateway: PaymentGatewayDep
) -> SuccessResponse[DuesPaymentRead]:
    payment = DuesService(db, gateway).pay_mine(current_user)
    return SuccessResponse(message=DuesMessages.LINK_CREATED, data=payment)


@dues_router.get("/businesses/{business_id}/dues", response_model=SuccessResponse[DuesSummaryRead])
def business_dues(
    business_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DuesSummaryRead]:
    summary = DuesService(db).summary_for_business(business_id, current_user)
    return SuccessResponse(message=DuesMessages.RETRIEVED, data=summary)


@dues_router.post(
    "/businesses/{business_id}/dues/pay", response_model=SuccessResponse[DuesPaymentRead]
)
def pay_business_dues(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    gateway: PaymentGatewayDep,
) -> SuccessResponse[DuesPaymentRead]:
    payment = DuesService(db, gateway).pay_for_business(business_id, current_user)
    return SuccessResponse(message=DuesMessages.LINK_CREATED, data=payment)


@admin_router.get("/due", response_model=SuccessResponse[list[PayoutDueRead]])
def payouts_due(
    db: DbSessionDep, _admin: PayoutManagerDep, query: Annotated[PayoutDueQuery, Query()]
) -> SuccessResponse[list[PayoutDueRead]]:
    return SuccessResponse(message=PayoutMessages.DUE_RETRIEVED, data=PayoutService(db).due(query))


@admin_router.post("", response_model=SuccessResponse[PayoutRead])
def create_payout(
    payload: PayoutCreate, db: DbSessionDep, admin: PayoutManagerDep
) -> SuccessResponse[PayoutRead]:
    return SuccessResponse(
        message=PayoutMessages.CREATED, data=PayoutService(db).create(payload, admin)
    )


@admin_router.post("/bulk", response_model=SuccessResponse[list[PayoutRead]])
def create_all_payouts(
    payload: PayoutBulkCreate, db: DbSessionDep, admin: PayoutManagerDep
) -> SuccessResponse[list[PayoutRead]]:
    payouts = PayoutService(db).create_all(payload, admin)
    return SuccessResponse(message=PayoutMessages.BULK_CREATED, data=payouts)


@admin_router.get("", response_model=SuccessResponse[Page[PayoutRead]])
def list_payouts(
    db: DbSessionDep,
    _admin: PayoutManagerDep,
    params: PaginationDep,
    query: Annotated[PayoutListQuery, Query()],
) -> SuccessResponse[Page[PayoutRead]]:
    items, total = PayoutService(db).list_all(query, params)
    return SuccessResponse(
        message=PayoutMessages.LIST_RETRIEVED,
        data=Page[PayoutRead].create(items=items, total=total, params=params),
    )


@admin_router.get("/export")
def export_payouts(
    db: DbSessionDep, _admin: PayoutManagerDep, query: Annotated[PayoutListQuery, Query()]
) -> Response:
    return Response(
        content=PayoutService(db).export_csv(query),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="payouts.csv"'},
    )


@admin_router.get("/{payout_id}", response_model=SuccessResponse[PayoutDetailRead])
def get_payout(
    payout_id: UUID, db: DbSessionDep, _admin: PayoutManagerDep
) -> SuccessResponse[PayoutDetailRead]:
    return SuccessResponse(message=PayoutMessages.RETRIEVED, data=PayoutService(db).get(payout_id))


@admin_router.post("/{payout_id}/mark-paid", response_model=SuccessResponse[PayoutRead])
def mark_payout_paid(
    payout_id: UUID, payload: PayoutMarkPaid, db: DbSessionDep, admin: PayoutManagerDep
) -> SuccessResponse[PayoutRead]:
    payout = PayoutService(db).mark_paid(payout_id, payload, admin)
    return SuccessResponse(message=PayoutMessages.PAID, data=payout)


@admin_router.post("/{payout_id}/send", response_model=SuccessResponse[PayoutRead])
def send_payout(
    payout_id: UUID, db: DbSessionDep, admin: PayoutManagerDep, gateway: PayoutGatewayDep
) -> SuccessResponse[PayoutRead]:
    payout = PayoutService(db, gateway).send(payout_id, admin)
    return SuccessResponse(message=PayoutMessages.SENT, data=payout)


@admin_router.post("/{payout_id}/cancel", response_model=SuccessResponse[PayoutRead])
def cancel_payout(
    payout_id: UUID, db: DbSessionDep, admin: PayoutManagerDep
) -> SuccessResponse[PayoutRead]:
    return SuccessResponse(
        message=PayoutMessages.CANCELLED, data=PayoutService(db).cancel(payout_id, admin)
    )


@admin_dues_router.get("", response_model=SuccessResponse[list[DuesOwedRead]])
def dues_owed(db: DbSessionDep, _admin: PayoutManagerDep) -> SuccessResponse[list[DuesOwedRead]]:
    return SuccessResponse(
        message=DuesMessages.LIST_RETRIEVED, data=DuesService(db).owed_by_payee()
    )


@admin_dues_router.get("/payments", response_model=SuccessResponse[Page[DuesPaymentRead]])
def dues_payments(
    db: DbSessionDep, _admin: PayoutManagerDep, params: PaginationDep
) -> SuccessResponse[Page[DuesPaymentRead]]:
    items, total = DuesService(db).list_payments(params)
    return SuccessResponse(
        message=DuesMessages.PAYMENTS_RETRIEVED,
        data=Page[DuesPaymentRead].create(items=items, total=total, params=params),
    )


@webhook_router.post("/webhook", response_model=SuccessResponse[None])
def razorpayx_webhook(
    body: RawBodyDep,
    db: DbSessionDep,
    gateway: PayoutGatewayDep,
    x_razorpay_signature: Annotated[str, Header()],
) -> SuccessResponse[None]:
    PayoutService(db, gateway).record_webhook(body, x_razorpay_signature)
    return SuccessResponse(message=PayoutMessages.WEBHOOK_PROCESSED, data=None)


router = APIRouter()
for sub_router in (me_router, dues_router, admin_router, admin_dues_router, webhook_router):
    router.include_router(sub_router)
