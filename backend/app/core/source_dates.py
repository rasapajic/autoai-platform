"""Source date evidence, kept separate from AutoAI observation timestamps."""

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def source_date(value, *, field, semantics, zone=None, reference=None):
    """Preserve date-only precision; reject ambiguous or implausible timestamps."""
    now = reference or datetime.now(timezone.utc)
    raw = str(value or "").strip()
    if not raw or isinstance(value, bool):
        return None
    try:
        if re.fullmatch(r"\d{10}|\d{13}", raw):
            parsed = datetime.fromtimestamp(int(raw) / (1000 if len(raw) == 13 else 1), timezone.utc)
            precision = "second"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}", raw):
            parsed_date = date.fromisoformat(raw) if "-" in raw else datetime.strptime(raw, "%d.%m.%Y").date()
            if not date(2000, 1, 1) <= parsed_date <= now.astimezone(ZoneInfo(zone or "UTC")).date():
                return None
            return {"value": parsed_date.isoformat(), "precision": "date", "field": field,
                    "semantics": semantics, "raw": raw, "timezone": zone or "UTC", "observed_at": now.isoformat()}
        elif zone and (match := re.fullmatch(r"(Heute|Gestern),?\s+(\d{2}:\d{2})", raw, re.I)):
            local = now.astimezone(ZoneInfo(zone))
            day = local.date() - timedelta(days=match[1].lower() == "gestern")
            parsed = datetime.combine(day, datetime.strptime(match[2], "%H:%M").time(), ZoneInfo(zone))
            # A repeated/nonexistent daylight-saving hour is ambiguous.
            if parsed.replace(fold=0).utcoffset() != parsed.replace(fold=1).utcoffset():
                return None
            precision = "minute"
        else:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})", raw):
                return None
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            precision = "second" if re.search(r"T\d{2}:\d{2}:\d{2}", raw) else "minute"
        parsed = parsed.astimezone(timezone.utc)
        if not datetime(2000, 1, 1, tzinfo=timezone.utc) <= parsed <= now + timedelta(minutes=5):
            return None
        return {"value": parsed.isoformat(), "precision": precision, "field": field,
                "semantics": semantics, "raw": raw[:100], "observed_at": now.isoformat()}
    except (ValueError, OverflowError, OSError):
        return None


def clean_source_dates(values, reference):
    result = {}
    if not isinstance(values, dict):
        return result
    for key, allowed in (("published", {"published", "published_or_renewed"}), ("modified", {"modified"})):
        item = values.get(key)
        if not isinstance(item, dict) or not isinstance(item.get("semantics"), str) or item["semantics"] not in allowed:
            continue
        parsed = source_date(item.get("value"), field=str(item.get("field", ""))[:80],
                             semantics=item["semantics"], reference=reference,
                             zone=item.get("timezone") if isinstance(item.get("timezone"), str) and item["timezone"] in {"UTC", "Europe/Berlin", "Europe/Vienna"} else None)
        if parsed:
            # Minute precision must not be promoted to seconds during ingest.
            if parsed["precision"] != "date" and item.get("precision") == "minute":
                parsed["precision"] = "minute"
            parsed["raw"] = str(item.get("raw", parsed["raw"]))[:100]
            result[key] = parsed
    return result


def merge_source_dates(previous, incoming):
    return {**(previous if isinstance(previous, dict) else {}), **incoming}


def structured_card_dates(article):
    result = {}
    for key, prop in (("published", "datePublished"), ("modified", "dateModified")):
        node = article.select_one(f'time[itemprop="{prop}"], meta[itemprop="{prop}"]')
        if node is not None:
            entry = source_date(node.get("datetime") or node.get("content"), field=prop, semantics=key)
            if entry:
                result[key] = entry
    return result
