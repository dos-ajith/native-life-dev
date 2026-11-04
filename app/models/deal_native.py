from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.gis_village import GisVillage


class DealNative(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deal_natives"
    __table_args__ = (
        UniqueConstraint("deal_id", "village_id", name="uq_deal_natives_deal_id_village_id"),
        Index(
            "uq_deal_natives_one_primary",
            "deal_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        Index("ix_deal_natives_village_id_deal_id", "village_id", "deal_id"),
    )

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    village_id: Mapped[UUID] = mapped_column(ForeignKey("gis_villages.id", ondelete="RESTRICT"))
    is_primary: Mapped[bool] = mapped_column(Boolean(), default=False)

    village: Mapped[GisVillage] = relationship()
