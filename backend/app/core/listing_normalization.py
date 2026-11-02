"""Deterministic vehicle labels; external taxonomy IDs are never guessed."""

import re
import unicodedata
from urllib.parse import unquote, urlparse


def _words(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


_MAKES = (
    "Abarth", "Acura", "Aiways", "Aixam", "Alfa Romeo", "Alpina", "Alpine",
    "Aston Martin", "Audi", "Austin", "Bentley", "BMW", "Buick", "BYD",
    "Cadillac", "Chery", "Chevrolet", "Chrysler", "Citroën", "Corvette", "Cupra",
    "Dacia", "Daewoo", "Daihatsu", "Dodge", "DS Automobiles", "Ferrari",
    "Fiat", "Fisker", "Ford", "Fuso", "Geely", "Genesis", "GMC", "Honda",
    "Hummer", "Hyundai", "Infiniti", "Isuzu", "Iveco", "Jaguar", "Jeep",
    "Kia", "KTM", "Lada", "Lamborghini", "Lancia", "Land Rover", "Leapmotor",
    "Lexus", "Ligier", "Lincoln", "Lotus", "Lucid", "MAN", "Maserati",
    "Maybach", "Mazda", "McLaren", "Mercedes-Benz", "MG", "Microcar", "Mini",
    "Mitsubishi", "Morgan", "NIO", "Nissan", "Oldsmobile", "Opel", "ORA",
    "Pagani", "Panther Westwinds", "Peugeot", "Piaggio", "Polestar", "Pontiac", "Porsche", "Puch",
    "RAM", "Renault", "Rivian", "Rolls-Royce", "Rover", "Saab", "SEAT",
    "Škoda", "Smart", "SsangYong", "Subaru", "Suzuki", "Tesla", "Toyota",
    "Triumph", "Vanderhall", "Volkswagen", "Volvo", "XPENG",
)
MAKE_ALIASES = {_words(make): make for make in _MAKES}
MAKE_ALIASES.update({
    "vw": "Volkswagen", "mercedes": "Mercedes-Benz", "benz": "Mercedes-Benz",
    "landrover": "Land Rover", "alfa": "Alfa Romeo", "ds": "DS Automobiles",
    "panther": "Panther Westwinds",
})
_PREFIXES = sorted(MAKE_ALIASES, key=len, reverse=True)
_MULTIWORD_MODELS = (
    "range rover sport", "range rover evoque", "range rover velar", "range rover",
    "grand cherokee", "grand scenic", "land cruiser", "model 3", "model s",
    "model x", "model y", "mustang mach e", "mx 5", "cx 5", "cx 3", "c hr", "m go",
    "tiggo 4", "tiggo 7", "tiggo 8", "tiggo 9",
)
_NUMERIC_MODELS = {
    "Audi": {"50", "80", "90", "100", "200"},
    "Fiat": {"124", "125", "126", "127", "128", "130", "131", "132", "500", "600"},
    "Peugeot": {"106", "107", "108", "205", "206", "207", "208", "301", "306", "307", "308", "309", "405", "406", "407", "408", "508", "605", "607", "806", "807", "1007", "2008", "3008", "4007", "4008", "5008"},
    "Volvo": {"240", "244", "245", "340", "360", "440", "460", "480", "740", "760", "850", "940", "960"},
    "Toyota": {"86"}, "Porsche": {"356", "718", "911", "924", "928", "944", "968"},
}


def canonical_make(value) -> str | None:
    return MAKE_ALIASES.get(_words(str(value))) if value else None


def _display_model(value: str) -> str:
    display = {"mx 5": "MX-5", "cx 3": "CX-3", "cx 5": "CX-5", "c hr": "C-HR", "m go": "M.Go"}
    if value in display:
        return display[value]
    if re.fullmatch(r"[a-z]\d{1,3}|\d[a-z]", value):
        return value.upper()
    if re.fullmatch(r"\d+[a-z]+", value):
        return value
    return value.title()


def _title_identity(value: str) -> tuple[str | None, str | None]:
    text = _words(value)
    for prefix in _PREFIXES:
        if text == prefix or text.startswith(prefix + " "):
            tail = text[len(prefix):].strip()
            model = next((model for model in _MULTIWORD_MODELS if tail == model or tail.startswith(model + " ")), None)
            if not model and tail:
                model = tail.split()[0]
            # A headline containing only a make, year or sales phrase is not a model.
            is_year = model and re.fullmatch(r"(?:19|20)\d{2}", model) and model not in _NUMERIC_MODELS.get(MAKE_ALIASES[prefix], set())
            if model and (is_year or model in {"zu", "verkaufen", "verkauf", "te", "koop", "for", "sale"}):
                model = None
            return MAKE_ALIASES[prefix], _display_model(model) if model else None
    return None, None


def normalize_vehicle_fields(data: dict) -> dict:
    make = canonical_make(data.get("make"))
    inferred_make = inferred_model = None
    candidates = [data.get("title"), data.get("description")]
    path = unquote(urlparse(str(data.get("url") or "")).path)
    candidates.extend(reversed([part for part in path.split("/") if part]))
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        candidate_make, candidate_model = _title_identity(candidate)
        if candidate_make and (make is None or candidate_make == make):
            inferred_make, inferred_model = candidate_make, candidate_model
            if candidate_model:
                break
    make = make or inferred_make

    raw_model = str(data.get("model") or "").strip()
    model = None
    if make and raw_model:
        if raw_model.isdigit():
            if raw_model in _NUMERIC_MODELS.get(make, set()) or raw_model == inferred_model:
                model = raw_model
        elif any(character.isalpha() for character in raw_model):
            model = re.sub(r"\s+\d+[.,]\d+\b.*$", "", raw_model)
            model = re.sub(r"\s+(?:TDI|TFSI|TSI|CDI|HDi|dCi|DSG|quattro|xDrive|4Motion|MHEV|PHEV)\b.*$", "", model, flags=re.I).strip()
            model = _display_model(_words(model))
    if not model and make:
        model = inferred_model
    return {"make": make, "model": model or None}
