from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from html.parser import HTMLParser
import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, Wishlist, WishlistItem
from app.realtime.manager import manager
from app.schemas.wishlist import (
    WishlistCreate,
    WishlistItemCreate,
    WishlistItemRead,
    WishlistRead,
    WishlistUpdate,
    WishlistItemUpdate,
    ProductPreviewRequest,
    ProductPreviewResponse,
)


router = APIRouter(prefix="/wishlists", tags=["wishlists"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[WishlistRead])
def list_wishlists(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
) -> list[Wishlist]:
    logger.info("list_wishlists called", extra={"user_id": current_user.id})
    response.headers["Cache-Control"] = "private, no-store"
    wishlists = db.query(Wishlist).filter(Wishlist.owner_id == current_user.id).all()
    return wishlists


@router.post("/", response_model=WishlistRead, status_code=status.HTTP_201_CREATED)
async def create_wishlist(
    payload: WishlistCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Wishlist:
    wishlist = Wishlist(
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
        cover_image_url=payload.cover_image_url,
        event_date=payload.event_date,
        is_public=payload.is_public,
        share_slug=_generate_share_slug(db),
    )
    db.add(wishlist)
    db.commit()
    db.refresh(wishlist)

    if wishlist.is_public:
        await manager.broadcast(
            f"friends:{wishlist.owner_id}",
            {
                "type": "FRIEND_WISHLISTS_DIRTY",
            },
        )

    return wishlist


@router.get("/{wishlist_id}", response_model=WishlistRead)
def get_wishlist(
    wishlist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Wishlist:
    wishlist = (
        db.query(Wishlist)
        .filter(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id)
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    return wishlist


@router.patch("/{wishlist_id}", response_model=WishlistRead)
async def update_wishlist(
    wishlist_id: int,
    payload: WishlistUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Wishlist:
    wishlist = (
        db.query(Wishlist)
        .filter(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id)
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(wishlist, key, value)

    db.add(wishlist)
    db.commit()
    db.refresh(wishlist)

    if wishlist.is_public:
        await manager.broadcast(
            f"friends:{wishlist.owner_id}",
            {
                "type": "FRIEND_WISHLISTS_DIRTY",
            },
        )

    return wishlist


@router.delete("/{wishlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wishlist(
    wishlist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    wishlist = (
        db.query(Wishlist)
        .filter(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id)
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    owner_id = wishlist.owner_id
    was_public = wishlist.is_public
    db.delete(wishlist)
    db.commit()

    if was_public:
        await manager.broadcast(
            f"friends:{owner_id}",
            {
                "type": "FRIEND_WISHLISTS_DIRTY",
            },
        )

    return None


@router.get("/{wishlist_id}/items", response_model=list[WishlistItemRead])
def list_items(
    wishlist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[WishlistItem]:
    wishlist = (
        db.query(Wishlist)
        .filter(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id)
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    items = (
        db.query(WishlistItem)
        .filter(WishlistItem.wishlist_id == wishlist_id, WishlistItem.is_deleted.is_(False))
        .all()
    )
    return items


@router.post("/{wishlist_id}/items", response_model=WishlistItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(
    wishlist_id: int,
    payload: WishlistItemCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WishlistItem:
    wishlist = (
        db.query(Wishlist)
        .filter(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id)
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    item = WishlistItem(
        wishlist_id=wishlist_id,
        title=payload.title,
        description=payload.description,
        url=payload.url,
        image_url=payload.image_url,
        price=payload.price,
        currency=payload.currency,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    if wishlist.is_public:
        await manager.broadcast(
            wishlist.share_slug,
            {
                "type": "ITEM_UPDATED",
                "item": WishlistItemRead.model_validate(item).model_dump(),
            },
        )

    return item


@router.patch("/{wishlist_id}/items/{item_id}", response_model=WishlistItemRead)
async def update_item(
    wishlist_id: int,
    item_id: int,
    payload: WishlistItemUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WishlistItem:
    wishlist = (
        db.query(Wishlist)
        .filter(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id)
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.id == item_id, WishlistItem.wishlist_id == wishlist.id)
        .first()
    )
    if not item or item.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)

    db.add(item)
    db.commit()
    db.refresh(item)

    if wishlist.is_public:
        await manager.broadcast(
            wishlist.share_slug,
            {
                "type": "ITEM_UPDATED",
                "item": WishlistItemRead.model_validate(item).model_dump(),
            },
        )

    return item


@router.delete("/{wishlist_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    wishlist_id: int,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    wishlist = (
        db.query(Wishlist)
        .filter(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id)
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.id == item_id, WishlistItem.wishlist_id == wishlist.id)
        .first()
    )
    if not item or item.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    item.is_deleted = True
    db.add(item)
    db.commit()
    db.refresh(item)

    if wishlist.is_public:
        await manager.broadcast(
            wishlist.share_slug,
            {
                "type": "ITEM_UPDATED",
                "item": WishlistItemRead.model_validate(item).model_dump(),
            },
        )

    return None


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.by_property: dict[str, str] = {}
        self.by_name: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        data = {key.lower(): value for key, value in attrs if value is not None}
        content = data.get("content")
        if not content:
            return
        prop = data.get("property")
        if prop:
            self.by_property[prop.lower()] = content
        name = data.get("name")
        if name:
            self.by_name[name.lower()] = content


def _fetch_product_preview(url: str) -> ProductPreviewResponse:
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(request, timeout=5) as response:
            status_code = response.getcode()
            if status_code and status_code >= 400:
                return ProductPreviewResponse(is_available=False)
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return ProductPreviewResponse()
            raw = response.read(200000)
    except (HTTPError, URLError, ValueError):
        return ProductPreviewResponse(is_available=False)

    try:
        html = raw.decode("utf-8", errors="ignore")
    except Exception:
        return ProductPreviewResponse()

    parser = _MetaParser()
    parser.feed(html)

    title = parser.by_property.get("og:title") or parser.by_name.get("title")
    description = parser.by_property.get("og:description") or parser.by_name.get("description")
    image_url = parser.by_property.get("og:image")

    price_str = (
        parser.by_property.get("product:price:amount")
        or parser.by_name.get("price")
        or parser.by_property.get("og:price:amount")
    )
    currency = (
        parser.by_property.get("product:price:currency")
        or parser.by_name.get("currency")
        or parser.by_property.get("og:price:currency")
    )

    price: float | None = None
    if price_str:
        try:
            price = float(price_str.replace(",", "."))
        except ValueError:
            price = None

    return ProductPreviewResponse(
        title=title,
        description=description,
        image_url=image_url,
        price=price,
        currency=currency,
    )


@router.post("/preview-url", response_model=ProductPreviewResponse)
def preview_item_url(
    payload: ProductPreviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductPreviewResponse:
    if not payload.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL is required",
        )
    _ = db
    preview = _fetch_product_preview(payload.url)
    return preview


def _generate_share_slug(db: Session) -> str:
    import secrets

    while True:
        slug = secrets.token_urlsafe(8)
        exists = db.query(Wishlist).filter(Wishlist.share_slug == slug).first()
        if not exists:
            return slug
