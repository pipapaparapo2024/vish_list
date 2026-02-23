from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Friend, User, Wishlist
from app.schemas.friend import FriendCreate, FriendRead
from app.schemas.wishlist import WishlistRead


router = APIRouter(prefix="/friends", tags=["friends"])


@router.get("/", response_model=list[FriendRead])
def list_friends(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[FriendRead]:
    friends = db.query(Friend).filter(Friend.user_id == current_user.id).all()
    result: list[FriendRead] = []
    for friend in friends:
        friend_user = db.query(User).filter(User.id == friend.friend_id).first()
        if not friend_user:
            continue
        result.append(
            FriendRead(
                id=friend.id,
                friend_id=friend.friend_id,
                friend_email=friend_user.email,
                friend_name=friend_user.name,
            ),
        )
    return result


@router.post("/", response_model=FriendRead, status_code=status.HTTP_201_CREATED)
def add_friend(
    payload: FriendCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FriendRead:
    friend_user = db.query(User).filter(User.email == payload.email).first()
    if not friend_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if friend_user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot add yourself as a friend")

    existing = (
        db.query(Friend)
        .filter(Friend.user_id == current_user.id, Friend.friend_id == friend_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already friends")

    friendship = Friend(user_id=current_user.id, friend_id=friend_user.id)
    reverse_friendship = Friend(user_id=friend_user.id, friend_id=current_user.id)
    db.add(friendship)
    db.add(reverse_friendship)
    db.commit()
    db.refresh(friendship)

    return FriendRead(
        id=friendship.id,
        friend_id=friend_user.id,
        friend_email=friend_user.email,
        friend_name=friend_user.name,
    )


@router.delete("/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(
    friend_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    friendship = (
        db.query(Friend)
        .filter(Friend.user_id == current_user.id, Friend.friend_id == friend_id)
        .first()
    )
    if not friendship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found")

    reverse_friendship = (
        db.query(Friend)
        .filter(Friend.user_id == friend_id, Friend.friend_id == current_user.id)
        .first()
    )

    db.delete(friendship)
    if reverse_friendship:
        db.delete(reverse_friendship)
    db.commit()


@router.get("/{friend_id}/public-wishlists", response_model=list[WishlistRead])
def get_friend_public_wishlists(
    friend_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Wishlist]:
    friendship = (
        db.query(Friend)
        .filter(Friend.user_id == current_user.id, Friend.friend_id == friend_id)
        .first()
    )
    if not friendship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found")

    wishlists = (
        db.query(Wishlist)
        .filter(Wishlist.owner_id == friend_id, Wishlist.is_public.is_(True))
        .all()
    )
    return wishlists

