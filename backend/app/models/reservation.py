from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("wishlist_items.id"), unique=True, index=True)
    reserver_display_name: Mapped[str] = mapped_column(String(255))
    reserver_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["WishlistItem"] = relationship(back_populates="reservation")


class Contribution(Base):
    __tablename__ = "contributions"
    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "contributor_display_name",
            "contributor_contact",
            name="uq_contribution_item_contributor",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("wishlist_items.id"), index=True)
    contributor_display_name: Mapped[str] = mapped_column(String(255))
    contributor_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["WishlistItem"] = relationship(back_populates="contributions")
