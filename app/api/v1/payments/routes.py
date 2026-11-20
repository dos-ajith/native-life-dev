from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import RedirectResponse

from app.api.deps import DbSessionDep, PaymentGatewayDep, SettingsDep
from app.core.messages import PaymentMessages
from app.core.openapi_tags import ApiTag
from app.core.payments import PaymentCallback
from app.plugins.deps import PluginRegistryDep
from app.schemas.payment import PaymentStatusRead
from app.schemas.response import SuccessResponse
from app.services.payment_event_service import PaymentEventService

router = APIRouter(prefix="/payments/razorpay", tags=[ApiTag.PAYMENTS])


async def read_raw_body(request: Request) -> bytes:
    return await request.body()


RawBodyDep = Annotated[bytes, Depends(read_raw_body)]


def _web_return(url: str, payment: PaymentStatusRead) -> RedirectResponse:
    query = urlencode(
        {
            "payment_subject": payment.subject.value,
            "payment_subject_id": str(payment.subject_id),
            "payment_status": payment.status.value,
        }
    )
    separator = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{separator}{query}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/callback", response_model=SuccessResponse[PaymentStatusRead])
def razorpay_payment_callback(
    db: DbSessionDep,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
    registry: PluginRegistryDep,
    razorpay_payment_id: Annotated[str, Query()],
    razorpay_payment_link_id: Annotated[str, Query()],
    razorpay_payment_link_reference_id: Annotated[str, Query()],
    razorpay_payment_link_status: Annotated[str, Query()],
    razorpay_signature: Annotated[str, Query()],
) -> SuccessResponse[PaymentStatusRead] | RedirectResponse:
    payment = PaymentEventService(db, gateway, registry).record_callback(
        PaymentCallback(
            link_id=razorpay_payment_link_id,
            reference=razorpay_payment_link_reference_id,
            status=razorpay_payment_link_status,
            payment_id=razorpay_payment_id,
            signature=razorpay_signature,
        )
    )
    if settings.payment_web_return_url:
        return _web_return(settings.payment_web_return_url, payment)
    return SuccessResponse(message=PaymentMessages.STATUS_RETRIEVED, data=payment)


@router.post("/webhook", response_model=SuccessResponse[None])
def razorpay_webhook(
    body: RawBodyDep,
    db: DbSessionDep,
    gateway: PaymentGatewayDep,
    registry: PluginRegistryDep,
    x_razorpay_signature: Annotated[str, Header()],
) -> SuccessResponse[None]:
    PaymentEventService(db, gateway, registry).record_webhook(body, x_razorpay_signature)
    return SuccessResponse(message=PaymentMessages.WEBHOOK_PROCESSED, data=None)
