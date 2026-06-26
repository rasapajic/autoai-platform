import re
from typing import Any


SPECIAL_VEHICLE_PATTERNS = [
    r"\bgepanzert\b",
    r"\barmored\b",
    r"\barmored\s+vehicle\b",
    r"\bbulletproof\b",
    r"\btrasco\b",
    r"\bbr\s*6\b",
    r"\bbr\s*7\b",
    r"\bprotection\b",
    r"\bsecurity\s+vehicle\b",
    r"\blimousine\s+service\s+conversion\b",
]


def is_special_vehicle_text(value: str | None) -> bool:
    if not value:
        return False
    text = str(value).lower()
    return any(re.search(pattern, text, re.I) for pattern in SPECIAL_VEHICLE_PATTERNS)


def is_special_vehicle(listing: Any) -> bool:
    parts = [
        getattr(listing, "make", None),
        getattr(listing, "model", None),
        getattr(listing, "variant", None),
        getattr(listing, "description", None),
        getattr(listing, "url", None),
    ]
    features = getattr(listing, "features", None) or []
    if isinstance(features, list):
        parts.extend(str(feature) for feature in features)
    else:
        parts.append(str(features))

    return is_special_vehicle_text(" ".join(str(part) for part in parts if part))
