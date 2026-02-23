from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Contribution, Reservation, Wishlist, WishlistItem
from app.realtime.manager import manager
from app.schemas.reservation import ContributionCreate, ContributionRead, ReservationCreate, ReservationRead
from app.schemas.wishlist import WishlistItemRead, WishlistRead


router = APIRouter(prefix="/public/wishlists", tags=["public-wishlists"])
logger = logging.getLogger(__name__)


@router.get("/{share_slug}", response_model=WishlistRead)
def get_public_wishlist(
    share_slug: str,
    db: Annotated[Session, Depends(get_db)],
) -> Wishlist:
    wishlist = db.query(Wishlist).filter(Wishlist.share_slug == share_slug, Wishlist.is_public.is_(True)).first()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    return wishlist


@router.get("/{share_slug}/items", response_model=list[WishlistItemRead])
def get_public_wishlist_items(
    share_slug: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[WishlistItem]:
    wishlist = db.query(Wishlist).filter(Wishlist.share_slug == share_slug, Wishlist.is_public.is_(True)).first()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    items = (
        db.query(WishlistItem)
        .filter(WishlistItem.wishlist_id == wishlist.id, WishlistItem.is_deleted.is_(False))
        .all()
    )
    return items


@router.get(
    "/{share_slug}/items/{item_id}",
    response_model=WishlistItemRead,
)
def get_public_wishlist_item(
    share_slug: str,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> WishlistItem:
    wishlist = db.query(Wishlist).filter(Wishlist.share_slug == share_slug, Wishlist.is_public.is_(True)).first()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    item = (
        db.query(WishlistItem)
        .filter(
            WishlistItem.id == item_id,
            WishlistItem.wishlist_id == wishlist.id,
            WishlistItem.is_deleted.is_(False),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return item


@router.post(
    "/{share_slug}/items/{item_id}/reserve",
    response_model=ReservationRead,
    status_code=status.HTTP_201_CREATED,
)
async def reserve_item(
    share_slug: str,
    item_id: int,
    payload: ReservationCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Reservation:
    logger.info(
        "reserve_item called",
        extra={
            "share_slug": share_slug,
            "item_id": item_id,
            "display_name": payload.display_name,
        },
    )

    try:
        wishlist = db.query(Wishlist).filter(Wishlist.share_slug == share_slug, Wishlist.is_public.is_(True)).first()
        if not wishlist:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

        item = (
            db.query(WishlistItem)
            .filter(
                WishlistItem.id == item_id,
                WishlistItem.wishlist_id == wishlist.id,
                WishlistItem.is_deleted.is_(False),
            )
            .first()
        )
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

        existing = db.query(Reservation).filter(Reservation.item_id == item.id).first()
        if existing:
            idempotency_key = request.headers.get("Idempotency-Key")
            if idempotency_key:
                logger.info(
                    "reserve_item idempotent hit",
                    extra={"share_slug": share_slug, "item_id": item_id},
                )
                return existing
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item is already reserved")

        reservation = Reservation(
            item_id=item.id,
            reserver_display_name=payload.display_name,
            reserver_contact=payload.contact,
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)

        db.refresh(item)
        await manager.broadcast(
            share_slug,
            {
                "type": "ITEM_UPDATED",
                "item": WishlistItemRead.model_validate(item).model_dump(),
            },
        )

        logger.info(
            "reserve_item succeeded",
            extra={"share_slug": share_slug, "item_id": item_id, "reservation_id": reservation.id},
        )

        return reservation
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception(
            "reserve_item failed with unexpected error",
            extra={"share_slug": share_slug, "item_id": item_id},
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc


@router.post(
    "/{share_slug}/items/{item_id}/contributions",
    response_model=ContributionRead,
    status_code=status.HTTP_201_CREATED,
)
async def contribute_to_item(
    share_slug: str,
    item_id: int,
    payload: ContributionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Contribution:
    logger.info(
        "contribute_to_item called",
        extra={
            "share_slug": share_slug,
            "item_id": item_id,
            "display_name": payload.display_name,
            "amount": float(payload.amount),
        },
    )

    try:
        wishlist = db.query(Wishlist).filter(Wishlist.share_slug == share_slug, Wishlist.is_public.is_(True)).first()
        if not wishlist:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

        item = (
            db.query(WishlistItem)
            .filter(
                WishlistItem.id == item_id,
                WishlistItem.wishlist_id == wishlist.id,
                WishlistItem.is_deleted.is_(False),
            )
            .first()
        )
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

        existing = (
            db.query(Contribution)
            .filter(
                Contribution.item_id == item.id,
                Contribution.contributor_display_name == payload.display_name,
                Contribution.contributor_contact == payload.contact,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already contributed to this item",
            )

        contribution = Contribution(
            item_id=item.id,
            contributor_display_name=payload.display_name,
            contributor_contact=payload.contact,
            amount=payload.amount,
        )
        db.add(contribution)
        db.commit()
        db.refresh(contribution)

        db.refresh(item)
        await manager.broadcast(
            share_slug,
            {
                "type": "ITEM_UPDATED",
                "item": WishlistItemRead.model_validate(item).model_dump(),
            },
        )

        logger.info(
          "contribute_to_item succeeded",
          extra={"share_slug": share_slug, "item_id": item_id, "contribution_id": contribution.id},
        )

        return contribution
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception(
            "contribute_to_item failed with unexpected error",
            extra={"share_slug": share_slug, "item_id": item_id},
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc
