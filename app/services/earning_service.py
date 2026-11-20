from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.orm import Session

from app.models.earning import Earning, EarningBeneficiary
from app.models.user import User
from app.repositories.earning_repository import EarningRepository, query_filters
from app.schemas.earning import (
    AdminEarningListQuery,
    EarningListQuery,
    EarningRead,
    EarningSummaryRead,
    EarningTotalsRead,
)
from app.schemas.pagination import PaginationParams
from app.services.business_service import BusinessService

PERSONAL_BENEFICIARIES = (
    EarningBeneficiary.PROMOTER,
    EarningBeneficiary.PROMOTER_COMMISSION,
    EarningBeneficiary.NATIVE_ADMIN,
    EarningBeneficiary.INDIVIDUAL_SELLER,
)


def _personal_scope(user_id: UUID) -> list[ColumnElement[bool]]:
    return [Earning.user_id == user_id, Earning.beneficiary_type.in_(PERSONAL_BENEFICIARIES)]


def _business_scope(business_id: UUID) -> list[ColumnElement[bool]]:
    return [
        Earning.business_id == business_id,
        Earning.beneficiary_type == EarningBeneficiary.BUSINESS,
    ]


def _admin_scope(query: AdminEarningListQuery) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if query.beneficiary_type is not None:
        filters.append(Earning.beneficiary_type == query.beneficiary_type)
    if query.business_id is not None:
        filters.append(Earning.business_id == query.business_id)
    if query.user_id is not None:
        filters.append(Earning.user_id == query.user_id)
    return filters


class EarningService:
    def __init__(self, db: Session) -> None:
        self._earnings = EarningRepository(db)
        self._businesses = BusinessService(db)

    def list_mine(
        self, actor: User, query: EarningListQuery, params: PaginationParams
    ) -> tuple[list[EarningRead], int]:
        return self._page(_personal_scope(actor.id) + query_filters(query), params)

    def summary_mine(self, actor: User, query: EarningListQuery) -> EarningSummaryRead:
        return self._summary(_personal_scope(actor.id) + query_filters(query))

    def list_for_business(
        self, business_id: UUID, actor: User, query: EarningListQuery, params: PaginationParams
    ) -> tuple[list[EarningRead], int]:
        business = self._businesses.get_for_actor(business_id, actor)
        return self._page(_business_scope(business.id) + query_filters(query), params)

    def summary_for_business(
        self, business_id: UUID, actor: User, query: EarningListQuery
    ) -> EarningSummaryRead:
        business = self._businesses.get_for_actor(business_id, actor)
        return self._summary(_business_scope(business.id) + query_filters(query))

    def list_all(
        self, query: AdminEarningListQuery, params: PaginationParams
    ) -> tuple[list[EarningRead], int]:
        return self._page(_admin_scope(query) + query_filters(query), params)

    def summary_all(self, query: AdminEarningListQuery) -> EarningSummaryRead:
        return self._summary(_admin_scope(query) + query_filters(query))

    def _page(
        self, filters: list[ColumnElement[bool]], params: PaginationParams
    ) -> tuple[list[EarningRead], int]:
        rows, total = self._earnings.page(filters, params)
        return [EarningRead.model_validate(row) for row in rows], total

    def _summary(self, filters: list[ColumnElement[bool]]) -> EarningSummaryRead:
        return EarningSummaryRead(
            totals=[
                EarningTotalsRead.model_validate(totals, from_attributes=True)
                for totals in self._earnings.totals(filters)
            ]
        )
