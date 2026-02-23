from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Wishlist
from app.realtime.manager import manager


router = APIRouter()


@router.websocket("/ws/wishlists/{share_slug}")
async def wishlist_ws(
    websocket: WebSocket,
    share_slug: str,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    wishlist = db.query(Wishlist).filter(Wishlist.share_slug == share_slug, Wishlist.is_public.is_(True)).first()
    if not wishlist:
        await websocket.close()
        return

    await manager.connect(share_slug, websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(share_slug, websocket)


@router.websocket("/ws/friends/{friend_id}")
async def friend_wishlists_ws(
    websocket: WebSocket,
    friend_id: int,
) -> None:
    slug = f"friends:{friend_id}"
    await manager.connect(slug, websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(slug, websocket)
