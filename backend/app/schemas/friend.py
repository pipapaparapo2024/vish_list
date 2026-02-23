from pydantic import BaseModel, EmailStr


class FriendCreate(BaseModel):
    email: EmailStr


class FriendRead(BaseModel):
    id: int
    friend_id: int
    friend_email: EmailStr
    friend_name: str | None

