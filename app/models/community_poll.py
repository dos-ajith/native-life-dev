from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timezone import naive_app_now
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class CommunityPoll(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "community_polls"
    __table_args__ = (
        Index("ix_community_polls_community_id_created_at", "community_id", "created_at"),
    )

    community_id: Mapped[UUID] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(String(500))
    allows_multiple: Mapped[bool] = mapped_column(
        Boolean(), server_default=sql_text("false"), default=False
    )
    show_results_before_vote: Mapped[bool] = mapped_column(
        Boolean(), server_default=sql_text("false"), default=False
    )
    ends_at: Mapped[datetime | None] = mapped_column(default=None)

    author: Mapped[User] = relationship()
    options: Mapped[list["CommunityPollOption"]] = relationship(
        order_by="CommunityPollOption.position", cascade="all, delete-orphan"
    )

    @property
    def is_closed(self) -> bool:
        return self.ends_at is not None and self.ends_at <= naive_app_now()


class CommunityPollOption(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "community_poll_options"
    __table_args__ = (Index("ix_community_poll_options_poll_id", "poll_id"),)

    poll_id: Mapped[UUID] = mapped_column(ForeignKey("community_polls.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer())
    votes_count: Mapped[int] = mapped_column(Integer(), server_default=sql_text("0"), default=0)


class CommunityPollVote(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "community_poll_votes"
    __table_args__ = (
        UniqueConstraint("option_id", "user_id", name="uq_community_poll_votes_option_id_user_id"),
        Index("ix_community_poll_votes_poll_id_user_id", "poll_id", "user_id"),
    )

    poll_id: Mapped[UUID] = mapped_column(ForeignKey("community_polls.id", ondelete="CASCADE"))
    option_id: Mapped[UUID] = mapped_column(
        ForeignKey("community_poll_options.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
