from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, defer, joinedload
from sqlalchemy.sql.base import ExecutableOption

from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.models.user_address import UserAddress


def _with_place() -> ExecutableOption:
    return joinedload(UserAddress.village).options(
        defer(GisVillage.geom),
        joinedload(GisVillage.taluk).options(
            defer(GisTaluk.geom),
            joinedload(GisTaluk.district).options(
                defer(GisDistrict.geom),
                joinedload(GisDistrict.state).options(defer(GisState.geom)),
            ),
        ),
    )


class UserAddressRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, address_id: UUID) -> UserAddress | None:
        stmt = select(UserAddress).options(_with_place()).where(UserAddress.id == address_id)
        return self._db.scalars(stmt).first()

    def list_by_user(self, user_id: UUID) -> list[UserAddress]:
        stmt = (
            select(UserAddress)
            .options(_with_place())
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.is_default.desc(), UserAddress.created_at)
        )
        return list(self._db.scalars(stmt))

    def count_by_user(self, user_id: UUID) -> int:
        stmt = select(func.count()).select_from(UserAddress).where(UserAddress.user_id == user_id)
        return self._db.scalar(stmt) or 0

    def latest_by_user(self, user_id: UUID) -> UserAddress | None:
        stmt = (
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.created_at.desc())
            .limit(1)
        )
        return self._db.scalar(stmt)

    def clear_default(self, user_id: UUID) -> None:
        self._db.execute(
            update(UserAddress)
            .where(UserAddress.user_id == user_id, UserAddress.is_default.is_(True))
            .values(is_default=False)
        )

    def add(self, address: UserAddress) -> UserAddress:
        self._db.add(address)
        self._db.flush()
        return address

    def delete(self, address: UserAddress) -> None:
        self._db.delete(address)
        self._db.flush()

    def commit(self) -> None:
        self._db.commit()
