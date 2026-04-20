from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.db import get_db
from app.core.auth import get_current_user
from app.models import Alert, User
from app.api.schemas import AlertCreate, AlertOut, MessageResponse

router = APIRouter()

MAX_ALERTS_FREE    = 3
MAX_ALERTS_PREMIUM = 20


@router.get("/", response_model=list[AlertOut])
def get_alerts(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    """Svi aktivni alertovi korisnika."""
    return (
        db.query(Alert)
        .filter(Alert.user_id == user.id, Alert.is_active == True)
        .order_by(Alert.created_at.desc())
        .all()
    )


@router.post("/", response_model=AlertOut, status_code=201)
def create_alert(
    data: AlertCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    """Kreiraj novi alert za pretragu."""
    # Limit po planu
    max_alerts = MAX_ALERTS_PREMIUM if user.is_premium else MAX_ALERTS_FREE
    current = db.query(Alert).filter(
        Alert.user_id == user.id,
        Alert.is_active == True,
    ).count()

    if current >= max_alerts:
        raise HTTPException(
            status_code=403,
            detail=f"Dostignut limit od {max_alerts} alerta. {'Nadogradi na Premium.' if not user.is_premium else ''}",
        )

    alert = Alert(
        user_id=user.id,
        name=data.name,
        filters=data.filters,
        frequency=data.frequency,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return AlertOut.model_validate(alert)


@router.delete("/{alert_id}", response_model=MessageResponse)
def delete_alert(
    alert_id: UUID,
    db:       Session = Depends(get_db),
    user:     User    = Depends(get_current_user),
):
    """Obriši alert."""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == user.id,
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert nije pronađen")

    alert.is_active = False
    db.commit()
    return MessageResponse(message="Alert obrisan")


@router.patch("/{alert_id}/toggle", response_model=AlertOut)
def toggle_alert(
    alert_id: UUID,
    db:       Session = Depends(get_db),
    user:     User    = Depends(get_current_user),
):
    """Uključi/isključi alert."""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == user.id,
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert nije pronađen")

    alert.is_active = not alert.is_active
    db.commit()
    db.refresh(alert)
    return AlertOut.model_validate(alert)
