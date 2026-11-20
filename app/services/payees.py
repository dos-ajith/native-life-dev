from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, and_

from app.models.earning import Earning, EarningBeneficiary
from app.models.payout import PayeeType

BENEFICIARIES_BY_PAYEE = {
    PayeeType.BUSINESS: (EarningBeneficiary.BUSINESS,),
    PayeeType.INDIVIDUAL_SELLER: (EarningBeneficiary.INDIVIDUAL_SELLER,),
    PayeeType.PROMOTER: (EarningBeneficiary.PROMOTER, EarningBeneficiary.PROMOTER_COMMISSION),
    PayeeType.NATIVE_ADMIN: (EarningBeneficiary.NATIVE_ADMIN,),
}
PAYEE_BY_BENEFICIARY = {
    beneficiary: payee
    for payee, beneficiaries in BENEFICIARIES_BY_PAYEE.items()
    for beneficiary in beneficiaries
}


@dataclass(frozen=True)
class PayeeKey:
    payee_type: PayeeType
    user_id: UUID | None
    business_id: UUID | None
    currency: str


def payee_key(earning: Earning) -> PayeeKey | None:
    payee_type = PAYEE_BY_BENEFICIARY.get(earning.beneficiary_type)
    if payee_type is None:
        return None
    if payee_type == PayeeType.BUSINESS:
        return PayeeKey(payee_type, None, earning.business_id, earning.currency)
    return PayeeKey(payee_type, earning.user_id, None, earning.currency)


def payee_filter(
    payee_type: PayeeType, user_id: UUID | None, business_id: UUID | None, currency: str
) -> ColumnElement[bool]:
    owner = (
        Earning.business_id == business_id
        if payee_type == PayeeType.BUSINESS
        else Earning.user_id == user_id
    )
    return and_(
        Earning.beneficiary_type.in_(BENEFICIARIES_BY_PAYEE[payee_type]),
        owner,
        Earning.currency == currency,
    )
