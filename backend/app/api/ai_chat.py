import json
import re
import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import settings
from app.core.db import get_db
from app.ai.import_calculator import ImportCalcRequest, calculate_import_cost, ai_import_advisor
from app.ai.fraud_detector import check_listing_fraud, get_risk_badge
from app.models import Listing

router = APIRouter()
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

_estimator = None
_semantic  = None

def get_estimator():
    global _estimator
    if _estimator is None:
        from app.ai.price_estimator import PriceEstimator
        _estimator = PriceEstimator.load()
    return _estimator

def get_semantic():
    global _semantic
    if _semantic is None:
        from app.ai.semantic_search import SemanticSearch
        _semantic = SemanticSearch()
    return _semantic

PARSE_SYSTEM = """Izvuci parametre pretrage automobila iz prirodnog teksta.
Vrati SAMO JSON bez ikakvog teksta okolo:
{"make":null,"model":null,"min_year":null,"max_year":null,
 "min_price":null,"max_price":null,"max_km":null,
 "fuel_type":null,"transmission":null,"body_type":null,"country":null}
Cene u EUR, km u celim brojevima, fuel: diesel/petrol/electric/hybrid/lpg"""

class QueryRequest(BaseModel):
    query: str

@router.post("/parse-query")
def parse_query(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(400, "Upit ne moze biti prazan")
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=300,
        system=PARSE_SYSTEM,
        messages=[{"role": "user", "content": req.query}],
    )
    try:
        filters = json.loads(message.content[0].text.strip())
    except Exception:
        match = re.search(r'\{.*\}', message.content[0].text, re.DOTALL)
        filters = json.loads(match.group()) if match else {}
    filters = {k: v for k, v in filters.items() if v is not None}
    parts = []
    if filters.get("make"):      parts.append(f"{filters['make']} {filters.get('model','')}")
    if filters.get("fuel_type"): parts.append(filters["fuel_type"])
    if filters.get("max_price"): parts.append(f"do {filters['max_price']:,} EUR")
    if filters.get("max_km"):    parts.append(f"max {filters['max_km']:,} km")
    return {"filters": filters, "original_query": req.query,
            "explanation": "Trazim: " + ", ".join(parts) if parts else "Prikazujem sve"}

class SemanticRequest(BaseModel):
    query:     str
    limit:     int = 10
    max_price: Optional[int] = None
    min_year:  Optional[int] = None
    fuel_type: Optional[str] = None
    country:   Optional[str] = None

@router.post("/semantic-search")
def semantic_search(req: SemanticRequest, db: Session = Depends(get_db)):
    filters = {k: v for k, v in {"max_price": req.max_price, "min_year": req.min_year,
               "fuel_type": req.fuel_type, "country": req.country}.items() if v is not None}
    results = get_semantic().semantic_search(query=req.query, db=db, limit=min(req.limit, 30), filters=filters)
    return {"results": results, "total": len(results)}

class EstimateRequest(BaseModel):
    make: str; model: str; year: int; mileage: int
    fuel_type: Optional[str] = None; transmission: Optional[str] = None
    country: Optional[str] = "DE"; engine_cc: Optional[int] = None

@router.post("/estimate-price")
def estimate_price(req: EstimateRequest):
    estimator = get_estimator()
    if not estimator.is_trained:
        raise HTTPException(503, "Model jos nije istreniran")
    return estimator.predict(req.model_dump())

@router.post("/import-cost")
def import_cost(req: ImportCalcRequest):
    return calculate_import_cost(req)

class ImportAdviceRequest(BaseModel):
    vehicle_description: str; from_country: str; to_country: str = "RS"

@router.post("/import-advice")
async def import_advice(req: ImportAdviceRequest):
    advice = await ai_import_advisor(req.vehicle_description, req.from_country, req.to_country)
    return {"advice": advice}

@router.get("/fraud-check/{listing_id}")
def fraud_check(listing_id: UUID, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Oglas nije pronadjen")
    result = check_listing_fraud(listing)
    return {"score": result.score, "risk_level": result.risk_level,
            "badge": get_risk_badge(result.risk_level),
            "red_flags": result.red_flags, "safe_signals": result.safe_signals}
