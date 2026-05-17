"""
analyze.py
----------
POST /api/v1/analyze/
"""

import re
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()

COUNTRY_LANG: dict[str, str] = {
    "DE": "Deutsch",  "AT": "Deutsch",  "CH": "Deutsch",
    "FR": "Français", "IT": "Italiano", "NL": "Nederlands",
    "BE": "Nederlands","ES": "Español", "DK": "Dansk",
    "SE": "Svenska",  "NO": "Norsk",   "PL": "Polski",
    "LU": "Français", "PT": "Português","CZ": "Čeština",
    "HU": "Magyar",   "SK": "Slovenčina",
}

# ── VAT Detection ─────────────────────────────────────────────────────────────

VAT_KEYWORDS = {
    "vat_deductible": [
        "mwst. ausweisbar", "mwst ausweisbar", "ust. ausweisbar",
        "mehrwertsteuer ausweisbar", "inkl. mwst", "inkl mwst",
        "vat deductible", "vat reclaimable", "net export",
        "export possible", "regelbesteuert", "regelbesteuerung",
        "netto export", "netto preis", "netto-preis",
    ],
    "no_vat": [
        "differenzbesteuerung", "differenzbesteuert",
        "margin scheme", "margin taxation",
        "privat", "privatverkauf", "private seller", "privatperson",
        "ohne mwst", "ohne mehrwertsteuer",
        "vat not deductible", "nicht ausweisbar",
        "kein vorsteuerabzug",
    ],
}

GERMAN_VAT = 0.19  # 19%

def _detect_vat_status(title: str, description: str, page_text: str) -> dict:
    combined = (
        (title or "") + " " +
        (description or "") + " " +
        (page_text or "")
    ).lower()

    for kw in VAT_KEYWORDS["vat_deductible"]:
        if kw in combined:
            return {"status": "vat_deductible", "keyword": kw}

    for kw in VAT_KEYWORDS["no_vat"]:
        if kw in combined:
            return {"status": "no_vat", "keyword": kw}

    return {"status": "unknown", "keyword": None}


def _calc_vat_info(price: int | None, vat_status: str) -> dict | None:
    if not price:
        return None
    if vat_status == "vat_deductible":
        net_estimate = round(price / (1 + GERMAN_VAT))
        saving = price - net_estimate
        return {
            "status":         "vat_deductible",
            "emoji":          "🟢",
            "label":          "Neto export moguć",
            "bruto_price":    price,
            "net_estimate":   net_estimate,
            "vat_saving":     saving,
            "disclaimer":     "Procena neto export cene. Potvrditi uslove sa prodavcem i pribaviti izvoznu dokumentaciju.",
        }
    if vat_status == "no_vat":
        return {
            "status":       "no_vat",
            "emoji":        "🔴",
            "label":        "PDV nije odbitljiv",
            "bruto_price":  price,
            "net_estimate": None,
            "vat_saving":   None,
            "disclaimer":   "Prodavac prodaje po Differenzbesteuerung ili kao privatno lice — PDV nije moguće odbiti za izvoz.",
        }
    return {
        "status":       "unknown",
        "emoji":        "🟠",
        "label":        "Potrebna potvrda prodavca",
        "bruto_price":  price,
        "net_estimate": None,
        "vat_saving":   None,
        "disclaimer":   "Nije jasno da li je moguć povrat PDV-a. Preporučujemo da pitate prodavca: 'Da li je moguća prodaja bez nemačkog PDV-a za izvoz u Srbiju?'",
    }


class AnalyzeRequest(BaseModel):
    url: str

class AnalyzeTextRequest(BaseModel):
    text: str
    url: Optional[str] = None


def _detect_source(url: str) -> Optional[str]:
    if "autoscout24" in url: return "autoscout24"
    if "mobile.de" in url:   return "mobile_de"
    return None


def _parse_price(text: str) -> Optional[int]:
    if not text: return None
    digits = re.sub(r"[^\d]", "", text)
    val = int(digits) if digits else None
    return val if val and val <= 2_000_000 else None


def _parse_mileage(text: str) -> Optional[int]:
    if not text: return None
    m = re.search(r"[\d.,]+", text)
    if not m: return None
    num = m.group(0)
    dot_count   = num.count(".")
    comma_count = num.count(",")
    if dot_count > 1 or comma_count > 1:
        clean = re.sub(r"[.,]", "", num)
    elif dot_count == 1 and comma_count == 0:
        parts = num.split(".")
        clean = num.replace(".", "") if len(parts[1]) == 3 else parts[0]
    elif comma_count == 1 and dot_count == 0:
        parts = num.split(",")
        clean = num.replace(",", "") if len(parts[1]) == 3 else parts[0]
    else:
        clean = re.sub(r"[.,]", "", num)
    val = int(clean) if clean else None
    return val if val and 1 <= val <= 999_999 else None


def _parse_year(text: str) -> Optional[int]:
    if not text: return None
    m = re.search(r"\b(19[5-9]\d|20[0-3]\d)\b", text)
    return int(m.group(1)) if m else None


def _parse_power_kw(text: str) -> Optional[int]:
    if not text: return None
    kw = re.search(r"(\d+)\s*kw", text.lower())
    if kw: return int(kw.group(1))
    ps = re.search(r"(\d+)\s*(ps|hp)", text.lower())
    if ps: return round(int(ps.group(1)) * 0.7355)
    return None


FUEL_MAP = {
    "diesel": "diesel", "dizel": "diesel",
    "petrol": "petrol", "benzin": "petrol", "gasoline": "petrol",
    "ethanol": "petrol", "flexifuel": "petrol",
    "electric": "electric", "elektro": "electric", "elektrisch": "electric",
    "hybrid": "hybrid", "plug-in hybrid": "hybrid",
    "lpg": "lpg", "autogas": "lpg",
    "cng": "cng", "erdgas": "cng",
}

def _normalize_fuel(text: str) -> Optional[str]:
    if not text: return None
    v = text.lower()
    for k, norm in FUEL_MAP.items():
        if k in v: return norm
    return None


def _calc_import_cost(price: int, carina_pct: float) -> dict:
    carina    = round(price * carina_pct / 100)
    pdv       = round((price + carina) * 0.20)
    transport = 420
    reg       = 280
    return {
        "eu_price":     price,
        "carina_pct":   carina_pct,
        "carina":       carina,
        "pdv":          pdv,
        "transport":    transport,
        "registration": reg,
        "total":        price + carina + pdv + transport + reg,
    }


AS24_JS = r"""
() => {
    const ldScripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
    let ldData = null;
    for (const s of ldScripts) {
        try {
            const d = JSON.parse(s.textContent);
            if (d['@type'] === 'Car' || d['@type'] === 'Vehicle' || d.offers) {
                ldData = d; break;
            }
        } catch {}
    }

    const priceEl = document.querySelector(
        '[data-type="price_block"] .cldt-price, .cldt-price, [class*="price-label"], [class*="PriceBlock"]'
    );
    let price_raw = priceEl ? priceEl.textContent.trim() : '';
    if (!price_raw && ldData?.offers?.price) price_raw = ldData.offers.price + ' €';

    const specs = {};
    document.querySelectorAll('[data-item-key]').forEach(el => {
        specs[el.getAttribute('data-item-key')] = el.textContent.trim();
    });
    document.querySelectorAll('dl').forEach(dl => {
        const dts = dl.querySelectorAll('dt');
        const dds = dl.querySelectorAll('dd');
        dts.forEach((dt, i) => {
            if (dds[i]) specs['dl__' + dt.textContent.trim()] = dds[i].textContent.trim();
        });
    });
    document.querySelectorAll('table tr').forEach(row => {
        const cells = row.querySelectorAll('td, th');
        if (cells.length >= 2) {
            const k = cells[0].textContent.trim();
            const v = cells[1].textContent.trim();
            if (k && v && k.length < 60) specs['tbl__' + k] = v;
        }
    });
    document.querySelectorAll('[data-cy], [data-testid]').forEach(el => {
        const key = el.getAttribute('data-cy') || el.getAttribute('data-testid');
        if (key && el.textContent.trim()) specs['cy__' + key] = el.textContent.trim();
    });

    const title = ldData?.name
        || document.querySelector('h1')?.textContent?.trim()
        || document.querySelector('[class*="title"]')?.textContent?.trim()
        || '';

    const locEl = document.querySelector(
        '[class*="seller-contact-country"], [class*="location"], [data-cy*="location"]'
    );
    const location_raw = locEl ? locEl.textContent.trim() : '';

    const images = Array.from(document.querySelectorAll(
        '.image-gallery-image img, [class*="gallery"] img, [class*="swiper"] img'
    )).map(i => i.src || i.getAttribute('data-src') || '')
      .filter(s => s && s.startsWith('http') && !s.includes('placeholder'));

    const desc = document.querySelector(
        '.cldt-stage-description, [class*="description"]'
    )?.textContent?.trim() || '';

    const features = Array.from(document.querySelectorAll(
        '.sc-expandable-element li, [class*="equipment"] li, [class*="feature"] li'
    )).map(e => e.textContent.trim()).filter(Boolean);

    const pageText = (document.body.innerText || '').slice(0, 10000);

    return { title, price_raw, specs, location_raw, images: images.slice(0,12), desc, features, ldData, pageText };
}
"""

async def _scrape_autoscout24(url: str) -> dict:
    from app.scrapers.autoscout24 import AutoScout24Scraper
    async with AutoScout24Scraper() as scraper:
        page = await scraper.get_page(url, wait_for=None)
        if not page:
            raise RuntimeError("Stranica nije učitana")
        await asyncio.sleep(3)
        try:
            raw = await page.evaluate(AS24_JS)
        finally:
            await page.close()

    specs     = raw.get("specs", {})
    page_text = raw.get("pageText", "")
    ld        = raw.get("ldData") or {}
    desc      = raw.get("desc", "") or ""
    title     = raw.get("title", "") or ld.get("name", "")

    price = _parse_price(raw.get("price_raw", ""))
    if not price and ld.get("offers", {}).get("price"):
        price = _parse_price(str(ld["offers"]["price"]))

    year = None
    for ld_key in ["dateVehicleFirstRegistered", "vehicleModelDate", "modelDate"]:
        if ld.get(ld_key):
            year = _parse_year(str(ld[ld_key]))
            if year: break
    if not year:
        for k, v in specs.items():
            if any(x in k.lower() for x in ["registr", "first", "zulassung", "baujahr", "erstzu"]):
                year = _parse_year(v)
                if year: break
    if not year:
        m = re.search(r'\b(0[1-9]|1[0-2])/(19[5-9]\d|20[0-3]\d)\b', page_text)
        if m: year = int(m.group(2))
    if not year:
        year = _parse_year(page_text[1000:5000])

    mileage = None
    if ld.get("mileageFromOdometer", {}).get("value"):
        mileage = _parse_mileage(str(ld["mileageFromOdometer"]["value"]))
    if not mileage:
        for k, v in specs.items():
            if any(x in k.lower() for x in ["km", "mileage", "kilomet", "laufleist"]):
                mileage = _parse_mileage(v)
                if mileage: break
    if not mileage:
        km_m = re.search(r"([\d.,]+)\s*km", page_text[:4000])
        if km_m: mileage = _parse_mileage(km_m.group(1) + " km")

    fuel_type = None
    if ld.get("fuelType"):
        fuel_type = _normalize_fuel(str(ld["fuelType"]))
    if not fuel_type:
        for k, v in specs.items():
            f = _normalize_fuel(v)
            if f: fuel_type = f; break
    if not fuel_type:
        fuel_type = _normalize_fuel(page_text[:2000])

    power_kw = None
    if ld.get("vehicleEngine", {}).get("enginePower"):
        power_kw = _parse_power_kw(str(ld["vehicleEngine"]["enginePower"]))
    if not power_kw:
        for k, v in specs.items():
            p = _parse_power_kw(v)
            if p: power_kw = p; break

    country, city = None, None
    loc = raw.get("location_raw", "")
    if not loc and ld.get("offers", {}).get("availableAtOrFrom", {}).get("address"):
        addr    = ld["offers"]["availableAtOrFrom"]["address"]
        city    = addr.get("addressLocality")
        country = addr.get("addressCountry")
    if loc:
        parts = [p.strip() for p in loc.replace("\n", ",").split(",")]
        parts = [p for p in parts if p]
        if len(parts) >= 2: country, city = parts[-1], parts[0]
        elif parts: city = parts[0]

    # VAT detection
    vat_raw = _detect_vat_status(title, desc, page_text)
    vat_info = _calc_vat_info(price, vat_raw["status"])

    return {
        "title":           title,
        "price":           price,
        "year":            year,
        "mileage":         mileage,
        "fuel_type":       fuel_type,
        "engine_power_kw": power_kw,
        "country":         country,
        "city":            city,
        "images":          raw.get("images", []),
        "description":     desc or ld.get("description"),
        "features":        raw.get("features", []),
        "vat_info":        vat_info,
        "vat_keyword":     vat_raw.get("keyword"),
    }


MDE_JS = r"""
() => {
    const ldScripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
    let ldData = null;
    for (const s of ldScripts) {
        try {
            const d = JSON.parse(s.textContent);
            if (d['@type'] === 'Car' || d['@type'] === 'Vehicle' || d.offers) {
                ldData = d; break;
            }
        } catch {}
    }

    const priceSelectors = [
        '[data-testid="prime-price"]', '[class*="price-block"] [class*="price"]',
        '[class*="PriceBlock"]', 'h2[class*="price"]', '[class*="price"]',
    ];
    let price_raw = '';
    for (const sel of priceSelectors) {
        const el = document.querySelector(sel);
        if (el && el.textContent.includes('€')) { price_raw = el.textContent.trim(); break; }
    }
    if (!price_raw && ldData?.offers?.price) price_raw = ldData.offers.price + ' €';

    const title = ldData?.name
        || document.querySelector('h1')?.textContent?.trim() || '';

    let images = [];
    const imgSelectors = ['[class*="gallery"] img', '[class*="Gallery"] img', '.media-gallery img'];
    for (const sel of imgSelectors) {
        const imgs = Array.from(document.querySelectorAll(sel))
            .map(i => i.src || i.getAttribute('data-src') || '')
            .filter(s => s && s.startsWith('http') && !s.includes('placeholder'));
        if (imgs.length > 0) { images = imgs.slice(0, 12); break; }
    }

    const specs = {};
    document.querySelectorAll('dl, table tr').forEach(row => {
        const cells = row.querySelectorAll('td, dt, dd, th');
        if (cells.length >= 2) {
            const k = cells[0].textContent.trim();
            const v = cells[1].textContent.trim();
            if (k && v && k.length < 50) specs[k] = v;
        }
    });

    const loc = document.querySelector('[data-testid="seller-location"], [class*="location"]')?.textContent?.trim() || '';
    const features = Array.from(document.querySelectorAll('[class*="equipment"] li, [class*="features"] li')).map(e => e.textContent.trim()).filter(Boolean);
    const pageText = (document.body.innerText || '').slice(0, 10000);

    return { title, price_raw, specs, location_raw: loc, images, ldData, features, pageText };
}
"""

async def _scrape_mobile_de(url: str) -> dict:
    from app.scrapers.mobile_de import MobileDeScraper
    async with MobileDeScraper() as scraper:
        page = await scraper.get_page(url, wait_for=None)
        if not page:
            raise RuntimeError("Stranica nije učitana")
        await asyncio.sleep(3)
        try:
            raw = await page.evaluate(MDE_JS)
        finally:
            await page.close()

    specs     = raw.get("specs", {})
    page_text = raw.get("pageText", "")
    ld        = raw.get("ldData") or {}
    title     = raw.get("title", "") or ld.get("name", "")

    price = _parse_price(raw.get("price_raw", ""))
    if not price and ld.get("offers", {}).get("price"):
        price = _parse_price(str(ld["offers"]["price"]))

    year = None
    for k, v in specs.items():
        if any(x in k.lower() for x in ["erst", "year", "zulassung", "baujahr", "registr"]):
            year = _parse_year(v)
            if year: break
    if not year and ld.get("vehicleModelDate"):
        year = _parse_year(str(ld["vehicleModelDate"]))
    if not year:
        m = re.search(r'\b(0[1-9]|1[0-2])/(19[5-9]\d|20[0-3]\d)\b', page_text)
        if m: year = int(m.group(2))
    if not year:
        year = _parse_year(page_text[:2000])

    mileage = None
    for k, v in specs.items():
        if "km" in k.lower() or "laufleistung" in k.lower():
            mileage = _parse_mileage(v)
            if mileage: break
    if not mileage and ld.get("mileageFromOdometer", {}).get("value"):
        mileage = _parse_mileage(str(ld["mileageFromOdometer"]["value"]))
    if not mileage:
        km_m = re.search(r"([\d.,]+)\s*km", page_text[:3000])
        if km_m: mileage = _parse_mileage(km_m.group(1) + " km")

    fuel_type = None
    for k, v in specs.items():
        if any(x in k.lower() for x in ["kraft", "fuel", "antrieb"]):
            fuel_type = _normalize_fuel(v)
            if fuel_type: break
    if not fuel_type and ld.get("fuelType"):
        fuel_type = _normalize_fuel(ld["fuelType"])
    if not fuel_type:
        fuel_type = _normalize_fuel(page_text[:2000])

    power_kw = None
    for k, v in specs.items():
        p = _parse_power_kw(v)
        if p: power_kw = p; break

    country, city = "DE", None
    loc = raw.get("location_raw", "")
    if loc:
        parts = [p.strip() for p in loc.replace("\n", ",").split(",")]
        parts = [p for p in parts if p]
        if parts: city = parts[0]

    # VAT detection
    vat_raw  = _detect_vat_status(title, "", page_text)
    vat_info = _calc_vat_info(price, vat_raw["status"])

    return {
        "title":           title,
        "price":           price,
        "year":            year,
        "mileage":         mileage,
        "fuel_type":       fuel_type,
        "engine_power_kw": power_kw,
        "country":         country,
        "city":            city,
        "images":          raw.get("images", []),
        "description":     ld.get("description"),
        "features":        raw.get("features", []),
        "vat_info":        vat_info,
        "vat_keyword":     vat_raw.get("keyword"),
    }


@router.post("/")
async def analyze_url(req: AnalyzeRequest):
    url    = req.url.strip()
    source = _detect_source(url)

    if not source:
        raise HTTPException(status_code=400, detail="Portal nije podržan. Koristite AutoScout24 ili Mobile.de URL.")

    try:
        if source == "autoscout24":
            data = await _scrape_autoscout24(url)
        else:
            data = await _scrape_mobile_de(url)
    except Exception as e:
        logger.error(f"[analyze] Scrape error for {url}: {e}")
        return {
            "scrape_success": False,
            "url":            url,
            "source":         source,
            "error_message":  "Nismo mogli automatski da pročitamo oglas.",
        }

    from app.core.serbia_import_rules import check_serbia_eligibility
    eligibility = check_serbia_eligibility(
        year      = data.get("year"),
        fuel_type = data.get("fuel_type"),
    )

    price       = data.get("price")
    import_cost = _calc_import_cost(price, eligibility.carina_pct) if price else None
    seller_lang = COUNTRY_LANG.get(data.get("country") or "", "Deutsch")

    risk_warnings: list[str] = list(eligibility.warnings)
    mileage = data.get("mileage")
    if mileage and mileage > 200_000:
        risk_warnings.append(f"Visoka kilometraža ({mileage:,} km) — proveri stanje motora i menjača.")
    if not data.get("year"):
        risk_warnings.append("Godište nije pronađeno — proveri datum prve registracije u oglasu.")
    if data.get("fuel_type") == "diesel":
        risk_warnings.append("Dizel vozilo — proveri stanje DPF filtera i turbine.")

    # VAT warning
    vat_info = data.get("vat_info")
    if vat_info and vat_info.get("status") == "unknown":
        risk_warnings.append("PDV status nepoznat — pitaj prodavca o mogućnosti neto izvoza.")

    return {
        "scrape_success":     True,
        "url":                url,
        "source":             source,
        "title":              data.get("title"),
        "year":               data.get("year"),
        "price":              price,
        "mileage":            mileage,
        "fuel_type":          data.get("fuel_type"),
        "engine_power_kw":    data.get("engine_power_kw"),
        "country":            data.get("country"),
        "city":               data.get("city"),
        "images":             data.get("images", []),
        "description":        data.get("description"),
        "features":           data.get("features", []),
        "vat_info":           vat_info,
        "serbia_eligibility": eligibility.to_dict(),
        "import_cost":        import_cost,
        "seller_language":    seller_lang,
        "risk_warnings":      risk_warnings,
    }


@router.post("/from-text")
async def analyze_from_text(req: AnalyzeTextRequest):
    import json
    import anthropic

    if not req.text or len(req.text.strip()) < 30:
        raise HTTPException(400, detail="Tekst je prekratak.")

    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": f"""Izvuci podatke o vozilu iz ovog teksta oglasa. Vrati SAMO validan JSON.

Tekst oglasa:
{req.text[:4000]}

Vrati JSON sa ovim poljima (null ako nije pronađeno):
{{
  "title": "pun naziv vozila",
  "year": 2019,
  "price": 26900,
  "mileage": 74125,
  "fuel_type": "diesel ili petrol ili electric ili hybrid ili lpg",
  "engine_power_kw": 110,
  "country": "DE",
  "city": "naziv grada"
}}"""
            }]
        )
        text = response.content[0].text.strip()
        text = re.sub(r"```json|```", "", text).strip()
        data = json.loads(text)
    except Exception as e:
        logger.error(f"[analyze/from-text] AI error: {e}")
        raise HTTPException(500, detail="Greška pri AI analizi teksta.")

    # VAT detection from pasted text
    vat_raw  = _detect_vat_status(data.get("title", ""), "", req.text)
    vat_info = _calc_vat_info(data.get("price"), vat_raw["status"])

    from app.core.serbia_import_rules import check_serbia_eligibility
    eligibility = check_serbia_eligibility(
        year      = data.get("year"),
        fuel_type = data.get("fuel_type"),
    )

    price       = data.get("price")
    import_cost = _calc_import_cost(price, eligibility.carina_pct) if price else None
    seller_lang = COUNTRY_LANG.get(data.get("country") or "", "Deutsch")

    risk_warnings: list[str] = list(eligibility.warnings)
    mileage = data.get("mileage")
    if mileage and mileage > 200_000:
        risk_warnings.append(f"Visoka kilometraža ({mileage:,} km) — proveri stanje motora.")
    if not data.get("year"):
        risk_warnings.append("Godište nije pronađeno u tekstu.")
    if data.get("fuel_type") == "diesel":
        risk_warnings.append("Dizel vozilo — proveri stanje DPF filtera i turbine.")

    return {
        "scrape_success":     True,
        "url":                req.url or "",
        "source":             "text_input",
        "title":              data.get("title"),
        "year":               data.get("year"),
        "price":              price,
        "mileage":            mileage,
        "fuel_type":          data.get("fuel_type"),
        "engine_power_kw":    data.get("engine_power_kw"),
        "country":            data.get("country"),
        "city":               data.get("city"),
        "images":             [],
        "description":        None,
        "features":           [],
        "vat_info":           vat_info,
        "serbia_eligibility": eligibility.to_dict(),
        "import_cost":        import_cost,
        "seller_language":    seller_lang,
        "risk_warnings":      risk_warnings,
    }
