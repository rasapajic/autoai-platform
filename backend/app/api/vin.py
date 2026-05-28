import httpx
import re
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# ✅ NHTSA vPIC API — besplatan, bez API ključa
NHTSA_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{}?format=json"

# Mapiranje godišta po VIN poziciji 10
YEAR_MAP = {
    'A':1980,'B':1981,'C':1982,'D':1983,'E':1984,'F':1985,'G':1986,'H':1987,
    'J':1988,'K':1989,'L':1990,'M':1991,'N':1992,'P':1993,'R':1994,'S':1995,
    'T':1996,'V':1997,'W':1998,'X':1999,'Y':2000,'1':2001,'2':2002,'3':2003,
    '4':2004,'5':2005,'6':2006,'7':2007,'8':2008,'9':2009,'A':2010,'B':2011,
    'C':2012,'D':2013,'E':2014,'F':2015,'G':2016,'H':2017,'J':2018,'K':2019,
    'L':2020,'M':2021,'N':2022,'P':2023,'R':2024,'S':2025,'T':2026,
}

# WMI — Evropski proizvođači
EU_WMI = {
    'WBA':'BMW','WBS':'BMW','WBX':'BMW',
    'WDD':'Mercedes-Benz','WDB':'Mercedes-Benz',
    'WAU':'Audi','WA1':'Audi',
    'WVW':'Volkswagen','WV2':'Volkswagen','WV1':'Volkswagen',
    'VSS':'SEAT','VF1':'Renault','VF3':'Peugeot','VF7':'Citroën',
    'ZFA':'Fiat','ZFF':'Ferrari','ZAR':'Alfa Romeo',
    'TMB':'Skoda','TRU':'Audi',
    'SCC':'Lotus','SAJ':'Jaguar','SAL':'Land Rover',
    'YV1':'Volvo','YV2':'Volvo',
    'WP0':'Porsche','WP1':'Porsche',
    'UU1':'Dacia','VF1':'Renault',
    'XTA':'Lada','XTT':'Lada',
}

def validate_vin(vin: str) -> tuple[bool, str]:
    vin = vin.upper().strip().replace(' ', '')
    if len(vin) != 17:
        return False, f"VIN mora imati tačno 17 znakova (uneto: {len(vin)})"
    if not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', vin):
        return False, "VIN sadrži nedozvoljene znakove (I, O, Q nisu dozvoljeni)"
    return True, vin

def decode_year_from_vin(vin: str) -> Optional[int]:
    """Dekodira godište iz pozicije 10 VIN-a"""
    if len(vin) < 10:
        return None
    char = vin[9].upper()
    # Drugi ciklus (2010+) — pozicija 10 se ponavlja
    if char in 'ABCDEFGHJKLMNPRSTUVWXY':
        # Odredi da li je prvi (1980-2009) ili drugi ciklus (2010+)
        # Koristimo poziciju 7 i 8 za heuristiku, ali najsigurnije je NHTSA
        val = YEAR_MAP.get(char)
        return val
    elif char.isdigit():
        return YEAR_MAP.get(char)
    return None

def get_eu_make(vin: str) -> Optional[str]:
    """Detektuje marku iz WMI dela VIN-a"""
    wmi = vin[:3].upper()
    return EU_WMI.get(wmi) or EU_WMI.get(wmi[:2])

def normalize_fuel(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.lower()
    if 'electric' in raw or 'elektr' in raw:
        return 'electric'
    if 'hybrid' in raw:
        return 'hybrid'
    if 'diesel' in raw:
        return 'diesel'
    if 'gasoline' in raw or 'petrol' in raw or 'benzin' in raw:
        return 'petrol'
    if 'lpg' in raw or 'gas' in raw:
        return 'lpg'
    return raw

def get_nhtsa_field(results: list, var_name: str) -> Optional[str]:
    for item in results:
        if item.get('Variable') == var_name:
            val = item.get('Value', '')
            if val and val.lower() not in ('not applicable', 'null', '', 'none'):
                return val.strip()
    return None

def calc_serbia_eligibility(year: Optional[int], fuel: Optional[str]) -> dict:
    age = (2026 - year) if year else None
    
    if fuel == 'electric':
        return {
            'status': 'eligible', 'emoji': '🟢',
            'label': 'Može uvoz u Srbiju',
            'reason': 'Električna vozila su oslobođena carine (0%).',
            'carina_pct': 0,
        }
    if age is not None and age >= 30:
        return {
            'status': 'oldtimer', 'emoji': '🟣',
            'label': 'Oldtimer izuzetak',
            'reason': f'Vozilo ({year}) starije od 30 godina — poseban režim.',
            'carina_pct': 5,
        }
    if not year:
        return {
            'status': 'needs_check', 'emoji': '🟠',
            'label': 'Nepoznato godište',
            'reason': 'Potrebna provera Euro norme.',
            'carina_pct': 5,
        }
    if year >= 2015:
        return {
            'status': 'eligible', 'emoji': '🟢',
            'label': 'Može uvoz u Srbiju',
            'reason': f'Vozilo ({year}) — Euro 6, bez ograničenja.',
            'carina_pct': 5,
        }
    if year >= 2011:
        return {
            'status': 'eligible', 'emoji': '🟢',
            'label': 'Može uvoz u Srbiju',
            'reason': f'Vozilo ({year}) — Euro 5.',
            'carina_pct': 5,
        }
    if year >= 2006:
        return {
            'status': 'eligible', 'emoji': '🟢',
            'label': 'Može uvoz' + (' — proveri Euro 4' if fuel == 'diesel' else ''),
            'reason': f'Vozilo ({year}) — Euro 4, minimalni uslov.',
            'carina_pct': 5,
        }
    if year >= 2001:
        return {
            'status': 'needs_check', 'emoji': '🟠',
            'label': 'Potrebna provera Euro norme',
            'reason': f'Vozilo ({year}) — verovatno Euro 3.',
            'carina_pct': 5,
        }
    return {
        'status': 'not_eligible', 'emoji': '🔴',
        'label': 'Uvoz nije preporučljiv',
        'reason': f'Vozilo ({year}) ne ispunjava standarde.',
        'carina_pct': 5,
    }

def compare_with_listing(vin_data: dict, listing: dict) -> list:
    """Poredi VIN podatke sa podacima iz oglasa, vraća listu neslaganja"""
    mismatches = []

    # Godište
    vin_year = vin_data.get('year')
    listing_year = listing.get('year')
    if vin_year and listing_year:
        diff = abs(int(vin_year) - int(listing_year))
        if diff > 1:
            mismatches.append({
                'field': 'Godište',
                'severity': 'critical' if diff > 2 else 'warning',
                'vin_value': str(vin_year),
                'listing_value': str(listing_year),
                'message': f'VIN pokazuje {vin_year}, oglas navodi {listing_year} — razlika {diff} god.',
            })

    # Gorivo
    vin_fuel = vin_data.get('fuel_type')
    listing_fuel = listing.get('fuel_type')
    if vin_fuel and listing_fuel:
        if vin_fuel != listing_fuel:
            mismatches.append({
                'field': 'Gorivo',
                'severity': 'critical',
                'vin_value': vin_fuel,
                'listing_value': listing_fuel,
                'message': f'VIN pokazuje {vin_fuel}, oglas navodi {listing_fuel}.',
            })

    # Marka
    vin_make = vin_data.get('make', '').lower()
    listing_make = (listing.get('make') or '').lower()
    if vin_make and listing_make and vin_make not in listing_make and listing_make not in vin_make:
        mismatches.append({
            'field': 'Marka',
            'severity': 'critical',
            'vin_value': vin_data.get('make'),
            'listing_value': listing.get('make'),
            'message': f'VIN pokazuje {vin_data.get("make")}, oglas navodi {listing.get("make")}.',
        })

    return mismatches


class VinRequest(BaseModel):
    vin: str
    listing: Optional[dict] = None  # Opcionalno — za poređenje sa oglasom


@router.post("/decode")
async def decode_vin(req: VinRequest):
    # Validacija VIN-a
    valid, vin_or_error = validate_vin(req.vin)
    if not valid:
        return {"success": False, "error": vin_or_error}

    vin = vin_or_error
    result = {
        "success": True,
        "vin": vin,
        "source": "nhtsa",
        "make": None, "model": None, "year": None,
        "fuel_type": None, "body_type": None,
        "engine_displacement": None, "engine_power_kw": None,
        "drive_type": None, "plant_country": None,
        "wmi": vin[:3], "vds": vin[3:9], "vis": vin[9:],
        "eu_make_hint": get_eu_make(vin),
        "year_hint": decode_year_from_vin(vin),
    }

    # NHTSA API poziv
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(NHTSA_URL.format(vin))
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("Results", [])

                result["make"]               = get_nhtsa_field(items, "Make") or result["eu_make_hint"]
                result["model"]              = get_nhtsa_field(items, "Model")
                result["year"]               = get_nhtsa_field(items, "Model Year") or result["year_hint"]
                result["fuel_type"]          = normalize_fuel(get_nhtsa_field(items, "Fuel Type - Primary") or "")
                result["body_type"]          = get_nhtsa_field(items, "Body Class")
                result["engine_displacement"]= get_nhtsa_field(items, "Displacement (L)")
                result["engine_cylinders"]   = get_nhtsa_field(items, "Engine Number of Cylinders")
                result["drive_type"]         = get_nhtsa_field(items, "Drive Type")
                result["plant_country"]      = get_nhtsa_field(items, "Plant Country")
                result["manufacturer"]       = get_nhtsa_field(items, "Manufacturer Name")

                # Konvertuj godište u int
                if result["year"]:
                    try:
                        result["year"] = int(str(result["year"])[:4])
                    except:
                        result["year"] = result["year_hint"]

                # Ako NHTSA nema podatke (EU auto), koristi WMI hint
                if not result["make"]:
                    result["make"] = result["eu_make_hint"]
                if not result["year"]:
                    result["year"] = result["year_hint"]

                result["nhtsa_error_code"] = get_nhtsa_field(items, "Error Code")
                result["nhtsa_error_text"] = get_nhtsa_field(items, "Error Text")
    except Exception as e:
        result["nhtsa_error"] = str(e)
        # Fallback na lokalni decode
        result["make"]  = result["eu_make_hint"]
        result["year"]  = result["year_hint"]
        result["source"] = "local_decode"

    # Serbia eligibility
    year_int = int(result["year"]) if result["year"] else None
    result["serbia_eligibility"] = calc_serbia_eligibility(year_int, result["fuel_type"])

    # Poređenje sa oglasom (ako je prosleđen)
    if req.listing:
        mismatches = compare_with_listing(result, req.listing)
        result["mismatches"] = mismatches
        result["match_status"] = "critical" if any(m["severity"] == "critical" for m in mismatches) \
            else "warning" if mismatches else "ok"
        result["match_label"] = (
            "🔴 Neslaganje podataka" if result["match_status"] == "critical"
            else "🟠 Moguće neslaganje" if result["match_status"] == "warning"
            else "🟢 Podaci odgovaraju oglasu"
        )
    else:
        result["mismatches"] = []
        result["match_status"] = "no_listing"
        result["match_label"] = "—"

    # Arhitektura za budući CarVertical/AutoDNA
    result["history_providers"] = {
        "available": False,
        "note": "MVP faza — detaljna istorija vozila dolazi u sledećoj verziji",
        "future": ["CarVertical", "AutoDNA", "CARFAX"]
    }

    return result
