from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import hash_password, verify_password, create_token, get_current_user
from app.models import User, Favorite, Listing
from app.api.schemas import UserRegister, UserLogin, UserOut, Token, MessageResponse

router = APIRouter()


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
