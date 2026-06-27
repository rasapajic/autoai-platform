import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import hash_password, verify_password, create_token, get_current_user
from app.core.email import public_link, send_email
from app.models import User, Favorite, Listing, PasswordResetToken
from app.api.schemas import (
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    Token,
    UserLogin,
    UserOut,
    UserRegister,
)

router = APIRouter()

PASSWORD_RESET_TOKEN_BYTES = 32
PASSWORD_RESET_EXPIRE_MINUTES = 60
FORGOT_PASSWORD_MESSAGE = "Ako nalog postoji, poslat je link za reset lozinke."
INVALID_RESET_TOKEN_MESSAGE = "Link za reset lozinke nije ispravan ili je istekao."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/register", response_model=Token, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Registracija novog korisnika."""
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email već postoji"
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(str(user.id))
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Login — vraća JWT token."""
    user = db.query(User).filter(
        User.email == data.email,
        User.is_active == True,
    ).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pogrešan email ili lozinka",
        )

    token = create_token(str(user.id))
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Pokretanje resetovanja lozinke bez otkrivanja da li email postoji."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)

    now = _utcnow()
    existing_tokens = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .all()
    )
    for existing_token in existing_tokens:
        existing_token.used_at = now

    token = secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(token),
        expires_at=now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
    )
    db.add(reset_token)
    db.commit()

    try:
        reset_url = public_link(f"/reset-password?token={token}")
        send_email(
            user.email,
            "AutoAI reset lozinke",
            (
                "Zdravo,\n\n"
                "Dobili smo zahtev za reset lozinke za tvoj AutoAI nalog.\n\n"
                f"Link za reset lozinke važi {PASSWORD_RESET_EXPIRE_MINUTES} minuta:\n"
                f"{reset_url}\n\n"
                "Ako nisi tražio reset lozinke, možeš ignorisati ovaj email.\n\n"
                "AutoAI"
            ),
        )
    except Exception:
        pass

    return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset lozinke pomoću važećeg jednokratnog tokena."""
    now = _utcnow()
    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == _hash_reset_token(data.token),
            PasswordResetToken.used_at.is_(None),
        )
        .first()
    )

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_TOKEN_MESSAGE,
        )

    if _as_utc(reset_token.expires_at) <= now:
        reset_token.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_TOKEN_MESSAGE,
        )

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        reset_token.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_TOKEN_MESSAGE,
        )

    user.password_hash = hash_password(data.password)
    user.is_active = True
    user.updated_at = now

    open_tokens = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .all()
    )
    for open_token in open_tokens:
        open_token.used_at = now

    db.commit()
    return MessageResponse(message="Lozinka je uspešno promenjena.")


@router.get("/me", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)):
    """Profil trenutno ulogovanog korisnika."""
    return UserOut.model_validate(user)


@router.get("/me/favorites")
def get_favorites(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    """Svi omiljeni oglasi korisnika."""
    favorites = (
        db.query(Listing)
        .join(Favorite, Favorite.listing_id == Listing.id)
        .filter(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )

    return [
        {
            "id":           str(l.id),
            "make":         l.make,
            "model":        l.model,
            "year":         l.year,
            "price":        float(l.price) if l.price else None,
            "mileage":      l.mileage,
            "country":      l.country,
            "images":       (l.images or [])[:1],
            "price_rating": l.price_rating,
            "url":          l.url,
            "special_vehicle": l.special_vehicle,
        }
        for l in favorites
    ]


@router.delete("/me", response_model=MessageResponse)
def delete_account(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    """Brisanje naloga."""
    user.is_active = False
    db.commit()
    return MessageResponse(message="Nalog deaktiviran")

@router.post("/me/favorites")
def add_favorite(
    data: dict,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    listing_id = data.get("listing_id")
    if not listing_id:
        raise HTTPException(status_code=400, detail="listing_id required")
    
    # Proveri da li već postoji
    existing = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.listing_id == listing_id,
    ).first()
    
    if existing:
        return {"message": "Već u favoritima"}
    
    fav = Favorite(user_id=user.id, listing_id=listing_id)
    db.add(fav)
    db.commit()
    return {"message": "Sačuvano"}
@router.delete("/me/favorites/{listing_id}")
def remove_favorite(
    listing_id: str,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.listing_id == listing_id,
    ).delete()
    db.commit()
    return {"message": "Uklonjeno"}
