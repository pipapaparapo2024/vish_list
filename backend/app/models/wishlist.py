from datetime import date, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Wishlist(Base):
    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_date: Mapped[date | None] = mapped_column(nullable=True)
    is_public: Mapped[bool] = mapped_column(default=True)
    share_slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="wishlists")
    items: Mapped[list["WishlistItem"]] = relationship(back_populates="wishlist", cascade="all, delete-orphan")


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    wishlist_id: Mapped[int] = mapped_column(ForeignKey("wishlists.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    wishlist: Mapped["Wishlist"] = relationship(back_populates="items")
    reservation: Mapped["Reservation | None"] = relationship(
        back_populates="item",
        uselist=False,
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["Contribution"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("wishlist_id", "id", name="uq_wishlist_item_per_wishlist"),)

    @property
    def is_reserved(self) -> bool:
        return self.reservation is not None

    @property
    def collected_amount(self) -> float:
        return float(sum(c.amount for c in self.contributions)) if self.contributions else 0.0

    @property
    def contributions_count(self) -> int:
        return len(self.contributions)

    @property
    def total_amount_target(self) -> float | None:
        return float(self.price) if self.price is not None else None
