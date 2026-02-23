from datetime import date, datetime

from pydantic import BaseModel


class WishlistBase(BaseModel):
    title: str
    description: str | None = None
    cover_image_url: str | None = None
    event_date: date | None = None
    is_public: bool = True


class WishlistCreate(WishlistBase):
    pass


class WishlistUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    event_date: date | None = None
    is_public: bool | None = None


class WishlistRead(WishlistBase):
    id: int
    share_slug: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WishlistItemBase(BaseModel):
    title: str
    description: str | None = None
    url: str | None = None
    image_url: str | None = None
    price: float | None = None
    currency: str | None = None


class WishlistItemCreate(WishlistItemBase):
    pass


class WishlistItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    url: str | None = None
    image_url: str | None = None
    price: float | None = None
    currency: str | None = None
    is_deleted: bool | None = None


class WishlistItemRead(WishlistItemBase):
    id: int
    wishlist_id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    is_reserved: bool
    collected_amount: float
    contributions_count: int
    total_amount_target: float | None

    class Config:
        from_attributes = True


class ProductPreviewRequest(BaseModel):
    url: str


class ProductPreviewResponse(BaseModel):
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    price: float | None = None
    currency: str | None = None
    is_available: bool = True
