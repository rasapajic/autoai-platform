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
    # Readable manufacturer names in the primary AutoScout24 make catalog.
    # These names do not provide a mapping for numeric source taxonomy codes.
    "BAIC", "Bugatti", "Caterham", "Changan", "DAF", "DFSK", "Dongfeng",
    "Donkervoort", "DR Automobiles", "GWM", "Haval", "Hongqi", "Ineos",
    "JAC", "Jaecoo", "Jetour", "KGM", "Lynk & Co", "Maxus", "Omoda",
    "Seres", "Skywell", "VinFast", "Zeekr", "Zhidou",
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
    "Omoda": {"5", "7", "9"}, "Jaecoo": {"5", "7", "8"}, "Lynk & Co": {"01", "02", "08"},
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


_JAGUAR_FAMILIES = {
    "f pace": "F-Pace", "f type": "F-Type", "e pace": "E-Pace",
    "e type": "E-Type", "i pace": "I-Pace", "s type": "S-Type",
    "x type": "X-Type", "c type": "C-Type", "d type": "D-Type",
    "xe": "XE", "xf": "XF", "xj": "XJ", "xj6": "XJ6",
    "xj12": "XJ12", "xjs": "XJS", "xjsc": "XJSC", "xjr": "XJR",
    "xk": "XK", "xk8": "XK8", "xkr": "XKR", "xk120": "XK120",
    "xk140": "XK140", "xk150": "XK150", "xj220": "XJ220",
    "xk 120": "XK120", "xk 140": "XK140", "xk 150": "XK150",
    "xj 220": "XJ220", "xj 6": "XJ6", "xj 12": "XJ12", "xk 8": "XK8",
}


def _jaguar_family(value: str) -> str | None:
    words = _words(value)
    return next((_JAGUAR_FAMILIES[name] for name in sorted(_JAGUAR_FAMILIES, key=len, reverse=True)
                 if words == name or words.startswith(name + " ")), None)


def evidenced_jaguar_model(data: dict) -> str | None:
    """Resolve known families, never expand a lone letter without named evidence.

    All readable headline/URL evidence must agree. Historic names outside this
    small repair vocabulary are left to the existing normalizer unchanged.
    """
    if canonical_make(data.get("make")) != "Jaguar":
        return None
    raw = _words(str(data.get("model") or ""))
    raw_family = _jaguar_family(raw)
    path = unquote(urlparse(str(data.get("url") or "")).path)
    candidates = [data.get("title"), data.get("description")]
    candidates.extend(part for part in path.split("/") if part)
    evidence = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        words = _words(candidate)
        if words.startswith("jaguar "):
            family = _jaguar_family(words[len("jaguar "):])
            if family:
                evidence.add(family)
    classic_xk = {"XK120", "XK140", "XK150"}
    if len(evidence & classic_xk) == 1:
        # A generic XK slug does not contradict a fully named classic model.
        evidence.discard("XK")
    if raw == "xk" and len(evidence) == 1 and evidence <= classic_xk:
        return next(iter(evidence))
    if len(evidence) > 1 or (raw_family and evidence and raw_family not in evidence):
        return None
    if raw_family:
        return raw_family
    if len(evidence) == 1:
        family = next(iter(evidence))
        if not raw or (raw.isdigit() and len(raw) >= 5) or raw == "jaguar" or raw == _words(family).split()[0]:
            return family
    return None


def _title_identity(value: str) -> tuple[str | None, str | None]:
    text = _words(value)
    for prefix in _PREFIXES:
        if text == prefix or text.startswith(prefix + " "):
            tail = text[len(prefix):].strip()
            if MAKE_ALIASES[prefix] == "Jaguar" and (family := _jaguar_family(tail)):
                return "Jaguar", family
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

    if make == "Jaguar":
        family = evidenced_jaguar_model({**data, "make": make})
        if family:
            return {"make": make, "model": family}
        if inferred_model in _JAGUAR_FAMILIES.values():
            inferred_model = None

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
