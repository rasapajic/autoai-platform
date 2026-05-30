"""
inbox.py — AI Inbox API
POST   /api/v1/inbox/conversations          — nova konverzacija + slanje poruke
GET    /api/v1/inbox/conversations          — lista svih konverzacija korisnika
GET    /api/v1/inbox/conversations/{id}     — detalji + poruke
POST   /api/v1/inbox/conversations/{id}/reply — korisnik unosi odgovor prodavca
PUT    /api/v1/inbox/conversations/{id}/status — promeni status
DELETE /api/v1/inbox/conversations/{id}    — arhiviraj
"""

import re
import logging
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.db import get_db
from app.models import Conversation, Message, Listing, User

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Auth helper ────────────────────────────────────────────────────────────────

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Nije autorizovano")
    token = authorization.replace("Bearer ", "")
    try:
        import jwt
        from app.core.config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Nevažeći token")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Korisnik nije pronađen")
    return user


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateConversationRequest(BaseModel):
    listing_id:       Optional[str]  = None
    listing_title:    Optional[str]  = None
    listing_url:      Optional[str]  = None
    listing_price:    Optional[float] = None
    listing_source:   Optional[str]  = None
    seller_language:  Optional[str]  = "Deutsch"
    seller_country:   Optional[str]  = None
    message_content:  str             # Generisana AI poruka
    questions_asked:  list[str]       = []
    vin_requested:    bool            = False


class AddReplyRequest(BaseModel):
    content: str   # Tekst odgovora koji je prodavac poslao


class UpdateStatusRequest(BaseModel):
    status: str    # pending_send | sent | reply_received | vin_received | negotiating | closed | rejected


# ── AI analiza odgovora prodavca ───────────────────────────────────────────────

async def _ai_analyze_reply(content: str, conversation: Conversation) -> dict:
    """AI analizira odgovor prodavca i izvlači ključne informacije."""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic()

        prompt = f"""Analiziraj odgovor prodavca automobila i izvuci ključne informacije.

Oglas: {conversation.listing_title or 'N/A'}
Odgovor prodavca:
{content}

Vrati SAMO JSON:
{{
  "vin": "VIN broj ako je naveden, inače null",
  "price": numerička cena ako je navedena, inače null,
  "mileage": km ako je navedena, inače null,
  "service_history": true/false/null,
  "coc_document": true/false/null,
  "export_possible": true/false/null,
  "damage_mentioned": true/false,
  "damage_description": "opis oštećenja ili null",
  "still_available": true/false/null,
  "summary": "kratki sažetak odgovora na srpskom (2-3 rečenice)",
  "recommendation": "buy/skip/negotiate/verify",
  "recommendation_reason": "razlog na srpskom"
}}"""

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        text = re.sub(r"```json|```", "", text).strip()
        import json
        return json.loads(text)
    except Exception as e:
        logger.error(f"AI analiza odgovora greška: {e}")
        return {}


# ── Rute ──────────────────────────────────────────────────────────────────────

@router.post("/conversations")
async def create_conversation(
    req: CreateConversationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Kreiraj novu konverzaciju i sačuvaj prvu poruku."""

    # Validacija listing_id
    listing = None
    if req.listing_id:
        try:
            listing = db.query(Listing).filter(Listing.id == req.listing_id).first()
        except Exception:
            pass

    conv = Conversation(
        user_id         = user.id,
        listing_id      = listing.id if listing else None,
        listing_title   = req.listing_title or (f"{listing.make} {listing.model} {listing.year}" if listing else None),
        listing_url     = req.listing_url or (listing.url if listing else None),
        listing_price   = req.listing_price or (float(listing.price) if listing and listing.price else None),
        listing_source  = req.listing_source or (listing.source if listing else None),
        seller_language = req.seller_language,
        seller_country  = req.seller_country,
        status          = "sent",
        vin_requested   = req.vin_requested,
        last_message_at = datetime.utcnow(),
    )
    db.add(conv)
    db.flush()

    msg = Message(
        conversation_id = conv.id,
        direction       = "outbound",
        content         = req.message_content,
        language        = req.seller_language,
        questions_asked = req.questions_asked,
        vin_requested   = req.vin_requested,
        channel         = "manual",
    )
    db.add(msg)
    db.commit()
    db.refresh(conv)

    return _conv_to_dict(conv)


@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status: Optional[str] = None,
):
    """Lista svih konverzacija korisnika."""
    q = db.query(Conversation).filter(Conversation.user_id == user.id)
    if status:
        q = q.filter(Conversation.status == status)
    convs = q.order_by(Conversation.last_message_at.desc().nullslast()).all()
    return [_conv_to_dict(c, include_messages=False) for c in convs]


@router.get("/conversations/{conv_id}")
def get_conversation(
    conv_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Detalji konverzacije sa svim porukama."""
    conv = _get_conv(conv_id, user, db)
    return _conv_to_dict(conv, include_messages=True)


@router.post("/conversations/{conv_id}/reply")
async def add_reply(
    conv_id: str,
    req: AddReplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dodaj odgovor prodavca i pokreni AI analizu."""
    conv = _get_conv(conv_id, user, db)

    # AI analiza odgovora
    extracted = await _ai_analyze_reply(req.content, conv)

    # Sačuvaj poruku
    msg = Message(
        conversation_id = conv.id,
        direction       = "inbound",
        content         = req.content,
        ai_extracted    = extracted,
        is_read         = False,
    )
    db.add(msg)

    # Ažuriraj konverzaciju sa izvučenim podacima
    if extracted.get("vin"):
        conv.vin_received = extracted["vin"]
        conv.status = "vin_received"
    elif conv.status == "sent":
        conv.status = "reply_received"

    if extracted.get("price"):           conv.seller_confirmed_price    = extracted["price"]
    if extracted.get("mileage"):         conv.seller_confirmed_mileage  = extracted["mileage"]
    if extracted.get("service_history") is not None: conv.service_history_confirmed = extracted["service_history"]
    if extracted.get("coc_document")    is not None: conv.coc_document_confirmed    = extracted["coc_document"]
    if extracted.get("export_possible") is not None: conv.export_possible_confirmed = extracted["export_possible"]
    if extracted.get("damage_mentioned"):
        conv.damage_mentioned     = True
        conv.damage_description   = extracted.get("damage_description")
    if extracted.get("summary"):         conv.ai_summary        = extracted["summary"]
    if extracted.get("recommendation"):  conv.ai_recommendation = extracted["recommendation"]

    conv.last_message_at = datetime.utcnow()
    db.commit()
    db.refresh(conv)

    return {**_conv_to_dict(conv, include_messages=True), "ai_extracted": extracted}


@router.put("/conversations/{conv_id}/status")
def update_status(
    conv_id: str,
    req: UpdateStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    allowed = {"pending_send","sent","reply_received","vin_received","negotiating","closed","rejected"}
    if req.status not in allowed:
        raise HTTPException(400, detail=f"Status mora biti jedan od: {allowed}")
    conv = _get_conv(conv_id, user, db)
    conv.status = req.status
    db.commit()
    return {"ok": True, "status": conv.status}


@router.delete("/conversations/{conv_id}")
def delete_conversation(
    conv_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = _get_conv(conv_id, user, db)
    db.delete(conv)
    db.commit()
    return {"ok": True}


@router.get("/conversations/stats/summary")
def inbox_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Statistika inbox-a za dashboard."""
    from sqlalchemy import func
    counts = dict(
        db.query(Conversation.status, func.count(Conversation.id))
        .filter(Conversation.user_id == user.id)
        .group_by(Conversation.status)
        .all()
    )
    unread = db.query(func.count(Message.id)).join(Conversation).filter(
        Conversation.user_id == user.id,
        Message.direction == "inbound",
        Message.is_read == False,
    ).scalar()

    return {
        "total":          sum(counts.values()),
        "sent":           counts.get("sent", 0),
        "reply_received": counts.get("reply_received", 0),
        "vin_received":   counts.get("vin_received", 0),
        "negotiating":    counts.get("negotiating", 0),
        "closed":         counts.get("closed", 0),
        "unread_replies": unread or 0,
        "by_status":      counts,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_conv(conv_id: str, user: User, db: Session) -> Conversation:
    conv = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.user_id == user.id,
    ).first()
    if not conv:
        raise HTTPException(404, detail="Konverzacija nije pronađena")
    return conv


def _conv_to_dict(conv: Conversation, include_messages: bool = False) -> dict:
    d = {
        "id":              str(conv.id),
        "listing_id":      str(conv.listing_id) if conv.listing_id else None,
        "listing_title":   conv.listing_title,
        "listing_url":     conv.listing_url,
        "listing_price":   float(conv.listing_price) if conv.listing_price else None,
        "listing_source":  conv.listing_source,
        "seller_language": conv.seller_language,
        "seller_country":  conv.seller_country,
        "status":          conv.status,
        "vin_requested":   conv.vin_received is not None or conv.vin_requested,
        "vin_received":    conv.vin_received,
        "vin_verified":    conv.vin_verified,
        "seller_confirmed_price":    float(conv.seller_confirmed_price) if conv.seller_confirmed_price else None,
        "seller_confirmed_mileage":  conv.seller_confirmed_mileage,
        "service_history_confirmed": conv.service_history_confirmed,
        "coc_document_confirmed":    conv.coc_document_confirmed,
        "export_possible_confirmed": conv.export_possible_confirmed,
        "damage_mentioned":          conv.damage_mentioned,
        "damage_description":        conv.damage_description,
        "ai_summary":        conv.ai_summary,
        "ai_recommendation": conv.ai_recommendation,
        "ai_score":          conv.ai_score,
        "created_at":        conv.created_at.isoformat() if conv.created_at else None,
        "updated_at":        conv.updated_at.isoformat() if conv.updated_at else None,
        "last_message_at":   conv.last_message_at.isoformat() if conv.last_message_at else None,
        "message_count":     len(conv.messages) if conv.messages else 0,
    }
    if include_messages:
        d["messages"] = [_msg_to_dict(m) for m in (conv.messages or [])]
    return d


def _msg_to_dict(msg: Message) -> dict:
    return {
        "id":             str(msg.id),
        "direction":      msg.direction,
        "content":        msg.content,
        "language":       msg.language,
        "questions_asked": msg.questions_asked or [],
        "vin_requested":  msg.vin_requested,
        "ai_extracted":   msg.ai_extracted,
        "created_at":     msg.created_at.isoformat() if msg.created_at else None,
        "is_read":        msg.is_read,
        "channel":        msg.channel,
    }
