import re

_ORIGIN_KEYWORDS = (
    "origin", "export", "pickup", "pre-carriage", "pre carriage",
    "pol", "load port", "loading port", "booking", "shipper",
)

_DESTINATION_KEYWORDS = (
    "destination", "import", "delivery", "arrival", "pod",
    "discharge port", "dest", "last mile", "consignee",
)


def rebucket_charges(quote_type: str, charges: list[dict]) -> list[dict]:
    normalized, _ = rebucket_charges_with_audit(quote_type, charges)
    return normalized


def rebucket_charges_with_audit(quote_type: str, charges: list[dict]) -> tuple[list[dict], list[dict]]:
    quote_type = (quote_type or "").strip().lower()
    normalized: list[dict] = []
    audit: list[dict] = []
    for charge in charges:
        item = dict(charge)
        before = str(item.get("category") or "").strip()
        reason = _rebucket_charge(item)
        normalized.append(item)
        after = str(item.get("category") or "").strip()
        if before != after:
            audit.append({
                "name_of_charge": item.get("name_of_charge", ""),
                "from_category": before,
                "to_category": after,
                "reason": reason,
            })
    return normalized, audit


def _rebucket_charge(charge: dict) -> str:
    name_norm = _norm(str(charge.get("name_of_charge") or ""))

    if _is_thc_like(name_norm):
        side = _detect_side(name_norm)
        if side == "origin":
            charge["category"] = "EXW / Origin Charges"
            return "thc-origin-side"
        if side == "destination":
            charge["category"] = "Destination Charges"
            return "thc-destination-side"

    return ""


def _is_thc_like(name_norm: str) -> bool:
    return (
        name_norm == "thc"
        or " thc " in f" {name_norm} "
        or "terminal handling" in name_norm
    )


def _detect_side(text: str) -> str:
    if any(k in text for k in _ORIGIN_KEYWORDS):
        return "origin"
    if any(k in text for k in _DESTINATION_KEYWORDS):
        return "destination"
    return ""


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()
