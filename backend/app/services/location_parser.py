import re
from urllib.parse import unquote


COUNTRY_WORDS = {
    "DE": ["germany", "deutschland"],
    "AT": ["austria", "osterreich", "österreich"],
    "FR": ["france", "frankreich"],
    "IT": ["italy", "italia", "italien"],
    "NL": ["netherlands", "nederland"],
    "BE": ["belgium", "belgique", "belgie", "belgien"],
    "RS": ["serbia", "srbija"],
}

KNOWN_CITIES = [
    "Berlin", "Hamburg", "München", "Munich", "Bremen", "Köln", "Cologne",
    "Frankfurt", "Stuttgart", "Düsseldorf", "Dortmund", "Essen", "Leipzig",
    "Dresden", "Hannover", "Nürnberg", "Wien", "Graz", "Linz", "Salzburg",
    "Innsbruck", "Klagenfurt", "St. Pölten", "Paris", "Lyon", "Marseille",
    "Toulouse", "Nice", "Milano", "Roma", "Torino", "Bologna", "Napoli",
    "Amsterdam", "Rotterdam", "Utrecht", "Brussels", "Bruxelles", "Antwerpen",
    "Beograd", "Novi Sad", "Niš",
]

NON_CITY_PATTERN = re.compile(
    r"(?i)\b("
    r"diesel|benzin|petrol|gasoline|hybrid|elektro|electric|lpg|cng|"
    r"bmw|mercedes|mercedes-benz|audi|volkswagen|vw|toyota|tesla|ford|opel|"
    r"renault|peugeot|citroen|fiat|skoda|seat|hyundai|kia|mazda|nissan|volvo|"
    r"km|kilometer|mileage|price|preis|eur|euro|ps|kw|"
    r"automatik|automatic|manual|schaltgetriebe|"
    r"limousine|kombi|suv|coupe|coupé|cabrio|hatchback|sedan"
    r")\b"
)


def parse_city(value: str | None, country: str | None = None) -> str | None:
    if not value:
        return None

    text = clean_location_text(value)
    if not text:
        return None

    postcode_city = re.search(r"\b\d{4,5}\s+([^\d,|/]{2,60})", text)
    if postcode_city:
        return normalize_city(postcode_city.group(1), country)

    for city in KNOWN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", text, re.I):
            return normalize_city(city, country)

    parts = [part.strip() for part in re.split(r"[,|/]", text) if part.strip()]
    for part in parts:
        city = normalize_city(part, country)
        if city:
            return city
    return None


def parse_city_from_url(url: str | None, country: str | None = None) -> str | None:
    if not url:
        return None
    text = unquote(str(url)).replace("-", " ").replace("_", " ")
    return parse_city(text, country)


def clean_location_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"(?i)\b(location|standort|seller|händler|dealer)\b[:\s]*", "", text)
    return text[:500]


def normalize_city(value: str | None, country: str | None = None) -> str | None:
    if not value:
        return None
    city = re.sub(r"\s+", " ", str(value).strip(" ,|-"))
    if not city or len(city) > 100:
        return None
    if re.fullmatch(r"\d+", city):
        return None
    if re.search(r"(?i)\b(https?|www|autoscout24|willhaben)\b", city):
        return None
    if ":" in city or "/" in city:
        return None
    if re.search(r"\d", city) or NON_CITY_PATTERN.search(city):
        return None
    if len(city.split()) > 4:
        return None
    if country and city.lower() in COUNTRY_WORDS.get(str(country).upper(), []):
        return None
    if city.lower() in {"germany", "deutschland", "austria", "osterreich", "österreich", "france", "italy", "italia", "netherlands", "belgium"}:
        return None
    return city[:100]
