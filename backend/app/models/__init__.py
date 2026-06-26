from sqlalchemy import (
    Column, String, Integer, Boolean, Text,
    DECIMAL, DateTime, ForeignKey, Date
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.core.db import Base
from app.services.special_vehicle import is_special_vehicle
import uuid


class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name          = Column(String(100))
    is_active     = Column(Boolean, default=True)
    is_premium    = Column(Boolean, default=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now())

    favorites     = relationship("Favorite", back_populates="user")
    alerts        = relationship("Alert", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")


class Listing(Base):
    __tablename__ = "listings"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id        = Column(String(200), unique=True, nullable=False)
    source             = Column(String(50), nullable=False)

    # Vozilo
    make               = Column(String(80))
    model              = Column(String(120))
    variant            = Column(String(120))
    year               = Column(Integer)
    # Cena
    price              = Column(DECIMAL(10, 2))
    currency           = Column(String(3), default="EUR")
    price_negotiable   = Column(Boolean, default=False)

    # Tehničke karakteristike
    mileage            = Column(Integer)
    fuel_type          = Column(String(30))
    transmission       = Column(String(30))
    engine_cc          = Column(Integer)
    engine_power_kw    = Column(Integer)
    body_type          = Column(String(40))
    color              = Column(String(50))
    doors              = Column(Integer)
    seats              = Column(Integer)

    # Lokacija
    country            = Column(String(60))
    city               = Column(String(100))
    postal_code        = Column(String(20))
    latitude           = Column(DECIMAL(9, 6))
    longitude          = Column(DECIMAL(9, 6))

    # Stanje
    condition          = Column(String(30))
    first_registration = Column(Date)
    owners_count       = Column(Integer)
    service_history    = Column(Boolean)
    accident_free      = Column(Boolean)

    # Sadržaj
    description        = Column(Text)
    images             = Column(JSONB, default=list)
    features           = Column(JSONB, default=list)

    # Meta
    url                = Column(Text, nullable=False)
    dealer_id          = Column(UUID(as_uuid=True), ForeignKey("dealers.id"), nullable=True)
    is_active          = Column(Boolean, default=True)
    first_seen_at      = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at       = Column(DateTime(timezone=True), server_default=func.now())
    scraped_at         = Column(DateTime(timezone=True), server_default=func.now())

    # AI
    # Kontakt
    contact_type       = Column(String(20), default="unknown")  # email | form | phone | unknown
    contact_url        = Column(Text)

    # AI
    price_estimated    = Column(DECIMAL(10, 2))
    price_delta_pct    = Column(DECIMAL(6, 2))
    price_rating       = Column(String(10))
    embedding          = Column(Vector(1536))

    # Relacije
    price_history = relationship("PriceHistory", back_populates="listing")
    dealer        = relationship("Dealer", back_populates="listings")
    conversations = relationship("Conversation", back_populates="listing")

    @property
    def special_vehicle(self):
        return is_special_vehicle(self)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id  = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"))
    price       = Column(DECIMAL(10, 2), nullable=False)
    currency    = Column(String(3), default="EUR")
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", back_populates="price_history")


class Dealer(Base):
    __tablename__ = "dealers"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id   = Column(String(100))
    source        = Column(String(50))
    name          = Column(String(200), nullable=False)
    country       = Column(String(60))
    city          = Column(String(100))
    address       = Column(Text)
    phone         = Column(String(50))
    website       = Column(Text)
    rating        = Column(DECIMAL(3, 2))
    reviews_count = Column(Integer, default=0)
    is_verified   = Column(Boolean, default=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    listings = relationship("Listing", back_populates="dealer")


class Alert(Base):
    __tablename__ = "alerts"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name         = Column(String(200))
    filters      = Column(JSONB, default=dict)
    is_active    = Column(Boolean, default=True)
    frequency    = Column(String(20), default="daily")
    last_sent_at = Column(DateTime(timezone=True))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="alerts")


class Favorite(Base):
    __tablename__ = "favorites"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user    = relationship("User", back_populates="favorites")
    listing = relationship("Listing")


class ScraperRun(Base):
    __tablename__ = "scraper_runs"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portal           = Column(String(50), nullable=False)
    status           = Column(String(20), default="running")
    listings_found   = Column(Integer, default=0)
    listings_new     = Column(Integer, default=0)
    listings_updated = Column(Integer, default=0)
    error_message    = Column(Text)
    started_at       = Column(DateTime(timezone=True), server_default=func.now())
    finished_at      = Column(DateTime(timezone=True))


# ────────────────────────────────────────────────────────────────────────────────
# AI INBOX — Conversation & Message modeli
# ────────────────────────────────────────────────────────────────────────────────

class Conversation(Base):
    """
    Jedna konverzacija = jedan korisnik + jedan oglas + prodavac.
    Čuva celu istoriju komunikacije, VIN status i AI analizu odgovora.
    """
    __tablename__ = "conversations"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="SET NULL"), nullable=True)

    # Osnove
    listing_title    = Column(String(300))          # Snapshot naziva oglasa
    listing_url      = Column(Text)                  # Direktan link na oglas
    listing_price    = Column(DECIMAL(10, 2))        # Snapshot cene
    listing_source   = Column(String(50))            # Portal (autoscout24, willhaben...)
    seller_language  = Column(String(20), default="Deutsch")
    seller_country   = Column(String(10))

    # Status konverzacije
    # pending_send | sent | reply_received | vin_received | negotiating | closed | rejected
    status       = Column(String(30), default="pending_send")

    # VIN tracking
    vin_requested  = Column(Boolean, default=False)
    vin_received   = Column(String(17))              # VIN koji je prodavac poslao
    vin_verified   = Column(Boolean)                 # Da li VIN odgovara oglasu
    vin_data       = Column(JSONB)                   # Dekodovani VIN podaci

    # Prikupljene informacije od prodavca
    seller_confirmed_price     = Column(DECIMAL(10, 2))
    seller_confirmed_mileage   = Column(Integer)
    service_history_confirmed  = Column(Boolean)
    coc_document_confirmed     = Column(Boolean)
    export_possible_confirmed  = Column(Boolean)
    damage_mentioned           = Column(Boolean)
    damage_description         = Column(Text)

    # AI analiza
    ai_summary        = Column(Text)                 # AI sažetak konverzacije
    ai_recommendation = Column(String(20))           # buy | skip | negotiate | verify
    ai_score          = Column(Integer)              # 0-100 poverenje u ponudu

    # Meta
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_message_at = Column(DateTime(timezone=True))

    # Relacije
    user     = relationship("User", back_populates="conversations")
    listing  = relationship("Listing", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation",
                           order_by="Message.created_at", cascade="all, delete-orphan")


class Message(Base):
    """
    Jedna poruka u konverzaciji.
    direction: 'outbound' (naš upit) | 'inbound' (odgovor prodavca)
    """
    __tablename__ = "messages"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)

    # Sadržaj
    direction = Column(String(10), nullable=False)   # outbound | inbound
    content   = Column(Text, nullable=False)
    language  = Column(String(20))                   # Jezik poruke

    # Pitanja koja su bila u poruci (outbound)
    questions_asked = Column(JSONB, default=list)    # Lista pitanja
    vin_requested   = Column(Boolean, default=False)

    # AI analiza (za inbound poruke)
    ai_extracted = Column(JSONB)  # Izvučeni podaci: {vin, price, mileage, service_history...}

    # Meta
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    is_read     = Column(Boolean, default=False)
    channel     = Column(String(20), default="manual")  # manual | gmail | whatsapp

    conversation = relationship("Conversation", back_populates="messages")
