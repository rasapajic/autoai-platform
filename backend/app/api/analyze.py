"""
analyze.py
----------
POST /api/v1/analyze/
Scrape-uje oglas sa AutoScout24 ili Mobile.de i vraća kompletnu analizu
za uvoz u Srbiju.
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


class AnalyzeRequest(BaseModel):
    url: str

class AnalyzeTextRequest(BaseModel):
    text: str
    url: Optional[str] = None


def _detect_source(url: str) -> Optional[str]:
    if "autoscout24" in url:
        return "autoscout24"
    if "mobile.de" in url:
        return "mobile_de"
    return None


def _parse_price(text: str) -> Optional[int]:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    val = int(digits) if digits else None
    return val if val and val <= 2_000_000 else None


def _parse_mileage(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"[\d.,]+", text)
    if not m:
        return None
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
    if not text:
        return None
    m = re.search(r"\b(19[5-9]\d|20[0-3]\d)\b", text)
    return int(m.group(1)) if m else None


def _parse_power_kw(text: str) -> Optional[int]:
    if not text:
        return None
    kw = re.search(r"(\d+)\s*kw", text.lower())
    if kw:
        return int(kw.group(1))
    ps = re.search(r"(\d+)\s*(ps|hp)", text.lower())
    if ps:
        return round(int(ps.group(1)) * 0.7355)
    return None


FUEL_MAP = {
    "diesel": "diesel", "dizel": "diesel",
    "petrol": "petrol", "benzin": "petrol", "gasoline": "petrol",
    "electric": "electric", "elektro": "electric", "elektrisch": "electric",
    "hybrid": "hybrid", "plug-in hybrid": "hybrid",
    "lpg": "lpg", "autogas": "lpg",
    "cng": "cng", "erdgas": "cng",
}

def _normalize_fuel(text: str) -> Optional[str]:
    if not text:
        return None
    v = text.lower()
    for k, norm in FUEL_MAP.items():
        if k in v:
            return norm
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
    const get  = sel => document.querySelector(sel)?.textContent?.trim() || '';
    const getA = sel => document.querySelector(sel)?.getAttribute('content') || '';

    const priceEl = document.querySelector(
        '[data-type="price_block"] .cldt-price, .cldt-price, [class*="price-label"], [class*="PriceBlock"]'
    );
    const price_raw = priceEl ? priceEl.textContent.trim() : '';

    const specs = {};
    document.querySelectorAll('[data-item-key]').forEach(el => {
        specs[el.getAttribute('data-item-key')] = el.textContent.trim();
    });

    document.querySelectorAll('dl dt, dl dd').forEach((el, i, arr) => {
        if (el.tagName === 'DT' && arr[i+1]?.tagName === 'DD') {
            specs['__' + el.textContent.trim()] = arr[i+1].textContent.trim();
        }
    });

    const title = get('h1') || get('[class*="title"]') || getA('og:title');

    const locEl = document.querySelector(
        '[class*="seller-contact-country"], [class*="SellerInfo"] [class*="address"], [class*="location"]'
    );
    const location_raw = locEl ? locEl.textContent.trim() : '';

    const images = Array.from(document.querySelectorAll(
        '.image-gallery-image img, [class*="gallery"] img, [class*="Gallery"] img'
    )).map(i => i.src || i.getAttribute('data-src')).filter(s => s && s.startsWith('http'));

    const desc = get('.cldt-stage-description, [class*="description"], [class*="Description"]');

    const features = Array.from(document.querySelectorAll(
        '.sc-expandable-element li, [class*="equipment"] li, [class*="Equipment"] li'
    )).map(e => e.textContent.trim()).filter(Boolean);

    const pageText = document.body.innerText || '';

    return { title, price_raw, specs, location_raw, images: images.slice(0,12), desc, features, pageText };
}
"""

async def _scrape_autoscout24(url: str) -> dict:
    from app.scrapers.autoscout24 import AutoScout24Scraper
    async with AutoScout24Scraper() as scraper:
        page = await scraper.get_page(url, wait_for=None)
        if not page:
            raise RuntimeError("Stranica nije učitana")
        try:
            raw = await page.evaluate(AS24_JS)
        finally:
            await page.close()

    specs     = raw.get("specs", {})
    page_text = raw.get("pageText", "")

    price = _parse_price(raw.get("price_raw", ""))

    year = None
    for k, v in specs.items():
        y = _parse_year(v)
        if y:
            year = y
            break
    if not year:
        year = _parse_year(page_text[:2000])

    mileage = None
    for k, v in specs.items():
        if "km" in k.lower() or "mileage" in k.lower() or "kilomet" in k.lower():
            mileage = _parse_mileage(v)
            if mileage:
                break
    if not mileage:
        km_m = re.search(r"([\d.,]+)\s*km", page_text[:3000])
        if km_m:
            mileage = _parse_mileage(km_m.group(1) + " km")

    fuel_type = None
    for k, v in specs.items():
        f = _normalize_fuel(v)
        if f:
            fuel_type = f
            break
    if not fuel_type:
        fuel_type = _normalize_fuel(page_text[:2000])

    power_kw = None
    for k, v in specs.items():
        p = _parse_power_kw(v)
        if p:
            power_kw = p
            break

    country, city = None, None
    loc = raw.get("location_raw", "")
    if loc:
        parts = [p.strip() for p in loc.replace("\n", ",").split(",")]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            country, city = parts[-1], parts[0]
        elif parts:
            city = parts[0]

    return {
        "title":           raw.get("title", ""),
        "price":           price,
        "year":            year,
        "mileage":         mileage,
        "fuel_type":       fuel_type,
        "engine_power_kw": power_kw,
        "country":         country,
        "city":            city,
        "images":          raw.get("images", []),
        "description":     raw.get("desc"),
        "features":        raw.get("features", []),
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
        '[data-testid="prime-price"]',
        '[class*="price-block"] [class*="price"]',
        '[class*="PriceBlock"]',
        '.price-rating__label',
        'h2[class*="price"]',
        '[class*="listing-price"]',
        '[class*="price"]',
    ];
    let price_raw = '';
    for (const sel of priceSelectors) {
        const el = document.querySelector(sel);
        if (el && el.textContent.includes('€')) { price_raw = el.textContent.trim(); break; }
    }
    if (!price_raw && ldData?.offers?.price) {
        price_raw = ldData.offers.price + ' €';
    }

    const title = ldData?.name
        || document.querySelector('h1[class*="title"], h1[class*="listing"], h1')?.textContent?.trim()
        || '';

    const imgSelectors = [
        '[class*="gallery"] img',
        '[class*="Gallery"] img',
        '[class*="image-gallery"] img',
        '.media-gallery img',
        'img[class*="main"]',
        'img[class*="vehicle"]',
    ];
    let images = [];
    for (const sel of imgSelectors) {
        const imgs = Array.from(document.querySelectorAll(sel))
            .map(i => i.src || i.getAttribute('data-src') || i.getAttribute('data-lazy') || '')
            .filter(s => s && s.startsWith('http') && !s.includes('placeholder') && !s.includes('logo'));
        if (imgs.length > 0) { images = imgs.slice(0, 12); break; }
    }
    if (images.length === 0 && ldData?.image) {
        images = Array.isArray(ldData.image) ? ldData.image : [ldData.image];
    }

    const specs = {};
    document.querySelectorAll('[class*="DataTable"] tr, [class*="data-table"] tr, dl, [class*="specs"] li, table tr').forEach(row => {
        const cells = row.querySelectorAll('td, dt, dd, th');
        if (cells.length >= 2) {
            const k = cells[0].textContent.trim();
            const v = cells[1].textContent.trim();
            if (k && v && k.length < 50) specs[k] = v;
        }
    });

    const loc = document.querySelector(
        '[data-testid="seller-location"], [class*="seller-location"], [class*="SellerInfo"] address, [class*="location"]'
    )?.textContent?.trim() || '';

    const features = Array.from(document.querySelectorAll(
        '[class*="equipment"] li, [class*="features"] li, [class*="highlight"] li'
    )).map(e => e.textContent.trim()).filter(Boolean);

    const pageText = (document.body.innerText || '').slice(0, 6000);

    return { title, price_raw, specs, location_raw: loc, images, ldData, features, pageText };
}
"""

async def _scrape_mobile_de(url: str) -> dict:
    from app.scrapers.mobile_de import MobileDeScraper
    async with MobileDeScraper() as scraper:
        page = await scraper.get_page(url, wait_for="domcontentloaded")
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

    price = _parse_price(raw.get("price_raw", ""))
    if not price and ld.get("offers", {}).get("price"):
        price = _parse_price(str(ld["offers"]["price"]))

    year = None
    for k, v in specs.items():
        if any(x in k.lower() for x in ["erst", "year", "zulassung", "baujahr", "registr"]):
            year = _parse_year(v)
            if year:
                break
    if not year and ld.get("vehicleModelDate"):
        year = _parse_year(str(ld["vehicleModelDate"]))
    if not year:
        year = _parse_year(page_text[:2000])

    mileage = None
    for k, v in specs.items():
        if "km" in k.lower() or "kilomet" in k.lower() or "laufleistung" in k.lower():
            mileage = _parse_mileage(v)
            if mileage:
                break
    if not mileage and ld.get("mileageFromOdometer", {}).get("value"):
        mileage = _parse_mileage(str(ld["mileageFromOdometer"]["value"]))
    if not mileage:
        km_m = re.search(r"([\d.,]+)\s*km", page_text[:3000])
        if km_m:
            mileage = _parse_mileage(km_m.group(1) + " km")

    fuel_type = None
    for k, v in specs.items():
        if any(x in k.lower() for x in ["kraft", "fuel", "energie", "antrieb"]):
            fuel_type = _normalize_fuel(v)
            if fuel_type:
                break
    if not fuel_type and ld.get("fuelType"):
        fuel_type = _normalize_fuel(ld["fuelType"])
    if not fuel_type:
        fuel_type = _normalize_fuel(page_text[:2000])

    power_kw = None
    for k, v in specs.items():
        p = _parse_power_kw(v)
        if p:
            power_kw = p
            break

    country, city = "DE", None
    loc = raw.get("location_raw", "")
    if loc:
        parts = [p.strip() for p in loc.replace("\n", ",").split(",")]
        parts = [p for p in parts if p]
        if parts:
            city = parts[0]

    title = raw.get("title", "") or ld.get("name", "")

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
    }


@router.post("/")
async def analyze_url(req: AnalyzeRequest):
    url    = req.url.strip()
    source = _detect_source(url)

    if not source:
        raise HTTPException(
            status_code=400,
            detail="Portal nije podržan. Koristite AutoScout24 ili Mobile.de URL.",
        )

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
            "error_message":  "Nismo mogli automatski da pročitamo oglas. "
                              "Kopiraj tekst oglasa ili ubaci screenshot.",
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
        risk_warnings.append(f"Visoka kilometraža ({mileage:,} km) — provjeri stanje motora i mjenjača.")
    if not data.get("year"):
        risk_warnings.append("Godište nije pronađeno — provjeri datum prve registracije u oglasu.")
    if data.get("fuel_type") == "diesel":
        risk_warnings.append("Dizel vozilo — provjeri stanje DPF filtera i turbine.")

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
        "serbia_eligibility": eligibility.to_dict(),
        "import_cost":        import_cost,
        "seller_language":    seller_lang,
        "risk_warnings":      risk_warnings,
    }


@router.post("/from-text")
async def analyze_from_text(req: AnalyzeTextRequest):
    """Analizira oglas iz zalijepljenog teksta koristeći Claude AI."""
    import json
    import anthropic

    if not req.text or len(req.text.strip()) < 30:
        raise HTTPException(400, detail="Tekst je prekratak. Zalijepi kompletan tekst oglasa.")

    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": f"""Izvuci podatke o vozilu iz ovog teksta oglasa. Vrati SAMO validan JSON, bez ikakvog drugog teksta.

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
        raise HTTPException(500, detail="Greška pri AI analizi teksta. Pokušaj ponovo.")

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
        risk_warnings.append(f"Visoka kilometraža ({mileage:,} km) — provjeri stanje motora.")
    if not data.get("year"):
        risk_warnings.append("Godište nije pronađeno u tekstu.")
    if data.get("fuel_type") == "diesel":
        risk_warnings.append("Dizel vozilo — provjeri stanje DPF filtera i turbine.")

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
        "serbia_eligibility": eligibility.to_dict(),
        "import_cost":        import_cost,
        "seller_language":    seller_lang,
        "risk_warnings":      risk_warnings,
    }
