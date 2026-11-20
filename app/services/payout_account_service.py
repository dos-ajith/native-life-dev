from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import get_settings
from app.core.encryption import FieldCipher
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.messages import BusinessMessages, PayoutAccountMessages
from app.models.payout_account import PayoutAccount
from app.models.user import User
from app.repositories.payout_repository import PayoutAccountRepository
from app.schemas.payout import PayoutAccountRead, PayoutAccountWrite, masked_account_number
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService

ENTITY_TYPE = "payout_account"
LAST_DIGITS = 4


def account_read(account: PayoutAccount) -> PayoutAccountRead:
    return PayoutAccountRead(
        account_holder_name=account.account_holder_name,
        account_number_masked=masked_account_number(account.account_number_last4),
        ifsc=account.ifsc,
        upi_id=account.upi_id,
        updated_at=account.updated_at,
    )


class PayoutAccountService:
    def __init__(self, db: Session) -> None:
        self._accounts = PayoutAccountRepository(db)
        self._businesses = BusinessService(db)
        self._activity_logs = ActivityLogService(db)

    def get_mine(self, actor: User) -> PayoutAccountRead:
        return account_read(self._require(self._accounts.personal(actor.id)))

    def save_mine(self, payload: PayoutAccountWrite, actor: User) -> PayoutAccountRead:
        return self._save(self._accounts.personal(actor.id), payload, actor, None)

    def get_for_business(self, business_id: UUID, actor: User) -> PayoutAccountRead:
        business = self._businesses.get_for_actor(business_id, actor)
        return account_read(self._require(self._accounts.for_business(business.id)))

    def save_for_business(
        self, business_id: UUID, payload: PayoutAccountWrite, actor: User
    ) -> PayoutAccountRead:
        business = self._businesses.get_for_actor(business_id, actor)
        if business.owner_id != actor.id:
            raise AuthorizationError(BusinessMessages.NOT_OWNER)
        return self._save(self._accounts.for_business(business.id), payload, actor, business.id)

    def _save(
        self,
        account: PayoutAccount | None,
        payload: PayoutAccountWrite,
        actor: User,
        business_id: UUID | None,
    ) -> PayoutAccountRead:
        cipher = FieldCipher.from_settings(get_settings())
        if account is None:
            account = self._accounts.add(
                PayoutAccount(
                    user_id=actor.id,
                    business_id=business_id,
                    account_holder_name=payload.account_holder_name,
                )
            )
        account.account_holder_name = payload.account_holder_name
        account.account_number_encrypted = (
            cipher.encrypt(payload.account_number) if payload.account_number else None
        )
        account.account_number_last4 = (
            payload.account_number[-LAST_DIGITS:] if payload.account_number else None
        )
        account.ifsc = payload.ifsc
        account.upi_id = payload.upi_id
        account.razorpayx_contact_id = None
        account.razorpayx_fund_account_id = None
        self._accounts.commit()
        self._accounts.refresh(account)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.PAYOUT_ACCOUNT_SAVED,
            entity_type=ENTITY_TYPE,
            entity_id=account.id,
            metadata={
                "business_id": str(business_id) if business_id else None,
                "has_bank_account": account.account_number_last4 is not None,
                "has_upi": account.upi_id is not None,
            },
        )
        return account_read(account)

    def _require(self, account: PayoutAccount | None) -> PayoutAccount:
        if account is None:
            raise NotFoundError(PayoutAccountMessages.NOT_FOUND)
        return account
