from datetime import datetime, timedelta
from typing import Annotated
import logging
import secrets
import smtplib
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import EmailCode, User
from app.schemas.user import (
    LoginCodeConfirm,
    LoginCodeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    Token,
    UserCreate,
    UserRead,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _generate_code() -> str:
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(4))


def _create_email_code(db: Session, email: str, purpose: str) -> str:
    code = _generate_code()
    code_hash = hash_password(code)
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    record = EmailCode(
        email=email,
        purpose=purpose,
        code_hash=code_hash,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    logger.info("Email code for %s (%s): %s", email, purpose, code)
    return code


def _send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        logger.warning(
            "SMTP is not configured; skipping email send to %s with subject %s",
            to_email,
            subject,
        )
        return
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            message = EmailMessage()
            message["From"] = settings.smtp_from
            message["To"] = to_email
            message["Subject"] = subject
            message.set_content(body)
            server.send_message(message)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Annotated[Session, Depends(get_db)]) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
        is_email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(str(user.id))
    return Token(access_token=access_token)


@router.post("/request-password-reset")
def request_password_reset(
    payload: PasswordResetRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return {"ok": True}
    code = _create_email_code(db, payload.email, "reset_password")
    _send_email(
        payload.email,
        "Код для сброса пароля",
        f"Ваш код для сброса пароля: {code}",
    )
    return {"ok": True}


@router.post("/confirm-password-reset", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm, db: Annotated[Session, Depends(get_db)]) -> None:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code or email")

    now = datetime.utcnow()
    code_record = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == payload.email,
            EmailCode.purpose == "reset_password",
            EmailCode.is_used.is_(False),
            EmailCode.expires_at > now,
        )
        .order_by(EmailCode.created_at.desc())
        .first()
    )
    if not code_record or not verify_password(payload.code, code_record.code_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code or email")

    user.hashed_password = hash_password(payload.new_password)
    code_record.is_used = True
    db.add(user)
    db.add(code_record)
    db.commit()


@router.post("/request-login-code")
def request_login_code(
    payload: LoginCodeRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return {"ok": True}
    code = _create_email_code(db, payload.email, "login")
    _send_email(
        payload.email,
        "Код для входа в Wishlist",
        f"Ваш код для входа: {code}",
    )
    return {"ok": True}


@router.post("/login-with-code", response_model=Token)
def login_with_code(payload: LoginCodeConfirm, db: Annotated[Session, Depends(get_db)]) -> Token:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or code")

    now = datetime.utcnow()
    code_record = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == payload.email,
            EmailCode.purpose == "login",
            EmailCode.is_used.is_(False),
            EmailCode.expires_at > now,
        )
        .order_by(EmailCode.created_at.desc())
        .first()
    )
    if not code_record or not verify_password(payload.code, code_record.code_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or code")

    user.is_email_verified = True
    code_record.is_used = True
    db.add(user)
    db.add(code_record)
    db.commit()

    access_token = create_access_token(str(user.id))
    return Token(access_token=access_token)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
