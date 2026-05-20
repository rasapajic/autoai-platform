from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
import re


# ─────────────────────────────────────────────────────────────
# LISTINGS
# ─────────────────────────────────────────────────────────────

class ListingBase(BaseModel):
    make:             Optional[str] = None
    model:            Optional[str] = None
    year:             Optional[int] = None
    price:            Optional[float] = None
    currency:         Optional[str] = "EUR"
    mileage:          Optional[int] = None
    fuel_type:        Optional[str] = None
    transmission:     Optional[str] = None
    engine_power_kw:  Optional[int] = None
    body_type:        Optional[str] = None
    color:            Optional[str] = None
    country:          Optional[str] = None
    city:             Optional[str] = None
    condition:        Optional[str] = None
    accident_free:    Optional[bool] = None
    service_history:  Optional[bool] = None


class ListingCard(ListingBase):
    id:               UUID
    source:           str
    images:           list = []
    url:              str
    price_estimated:  Optional[float] = None
    price_delta_pct:  Optional[float] = None
    price_rating:     Optional[str] = None
    first_seen_at:    Optional[datetime] = None

    @field_validator('images', mode='before')
    @classmethod
    def images_none_to_list(cls, v):
        return v if v is not None else []

    model_config = {"from_attributes": True}


class ListingDetail(ListingCard):
    variant:          Optional[str] = None
    engine_cc:        Optional[int] = None
    doors:            Optional[int] = None
    seats:            Optional[int] = None
    description:      Optional[str] = None
    features:         list = []
    first_registration: Optional[str] = None
    owners_count:     Optional[int] = None
    last_seen_at:     Optional[datetime] = None
    price_negotiable: Optional[bool] = None

    @field_validator('features', mode='before')
    @classmethod
    def features_none_to_list(cls, v):
        return v if v is not None else []

    model_config = {"from_attributes": True}


class PriceHistoryPoint(BaseModel):
    price:       float
    currency:    str
    recorded_at: datetime

    model_config = {"from_attributes": True}


class SearchFilters(BaseModel):
    query:        Optional[str] = None
    make:         Optional[str] = None
    model:        Optional[str] = None
    min_price:    Optional[int] = None
    max_price:    Optional[int] = None
    min_year:     Optional[int] = None
    max_year:     Optional[int] = None
    min_km:       Optional[int] = None
    max_km:       Optional[int] = None
    fuel_type:    Optional[str] = None
    transmission: Optional[str] = None
    body_type:    Optional[str] = None
    country:      Optional[str] = None
    price_rating: Optional[str] = None
    source:       Optional[str] = None
    sort_by:      str = "date"
    page:         int = 1
    limit:        int = 40

    @field_validator("limit")
    @classmethod
    def limit_max(cls, v):
        return min(v, 100)

    @field_validator("page")
    @classmethod
    def page_min(cls, v):
        return max(v, 1)


class SearchResponse(BaseModel):
    total:    int
    page:     int
    pages:    int
    results:  list[ListingCard]
    filters_applied: dict = {}


# ─────────────────────────────────────────────────────────────
# USERS & AUTH
# ─────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email:    EmailStr
    password: str
    name:     Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Lozinka mora imati najmanje 8 karaktera")
        return v


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserOut(BaseModel):
    id:         UUID
    email:      str
    name:       Optional[str] = None
    is_premium: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut


# ─────────────────────────────────────────────────────────────
# ALERTS
# ─────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    name:      str
    filters:   dict
    frequency: str = "daily"

    @field_validator("frequency")
    @classmethod
    def valid_frequency(cls, v):
        if v not in ("instant", "daily", "weekly"):
            raise ValueError("Mora biti: instant, daily ili weekly")
        return v


class AlertOut(BaseModel):
    id:          UUID
    name:        str
    filters:     dict
    frequency:   str
    is_active:   bool
    last_sent_at: Optional[datetime] = None
    created_at:  datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# GENERAL
# ─────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str

class StatsResponse(BaseModel):
    total_listings:  int
    active_listings: int
    portals:         dict
    top_makes:       list[dict]
    avg_price_eur:   Optional[float] = None
