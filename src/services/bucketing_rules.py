import re


_FREIGHT_UNITS = {
    "per kg",
    "per cbm",
    "per ton",
    "per container (20ft)",
    "per container (40ft)",
    "per container (40ft hc)",
}

_ORIGIN_KEYWORDS = (
    "origin",
    "export",
    "pickup",
    "pre-carriage",
    "pre carriage",
    "pol",
    "load port",
    "loading port",
    "booking",
    "shipper",
)

_DESTINATION_KEYWORDS = (
    "destination",
    "import",
    "delivery",
    "arrival",
    "pod",
    "discharge port",
    "dest",
    "last mile",
    "consignee",
)

_FCL_ORIGIN_NAMES = {
    "b/l fee",
    "port security",
    "port congestion",
    "telex release fee",
}

_FCL_FREIGHT_NAMES = {
    "ocean freight",
    "baf",
    "pss",
    "gri",
    "caf",
    "cic",
    "pcs",
    "emergency surcharge",
    "fuel surcharge",
}

_LCL_FREIGHT_NAMES = {
    "ocean freight",
    "baf",
    "emergency surcharge",
    "fuel surcharge",
}

_AIR_FREIGHT_NAMES = {
    "fuel surcharge",
    "security surcharge",
}


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
        reason = _rebucket_charge(quote_type, item)
        normalized.append(item)
        after = str(item.get("category") or "").strip()
        if before != after:
            audit.append({
                "name_of_charge": item.get("name_of_charge", ""),
                "from_category": before,
                "to_category": after,
                "reason": reason or "rebucketed",
            })
    return normalized, audit


def _rebucket_charge(quote_type: str, charge: dict):
    name = str(charge.get("name_of_charge") or "").strip()
    remarks = str(charge.get("remarks") or "").strip()
    unit = str(charge.get("unit_of_measurement") or "").strip().lower()
    category = str(charge.get("category") or "").strip()
    text = _norm(" ".join(part for part in (name, remarks, category) if part))
    name_norm = _norm(name)

    if _is_thc_like(name_norm, text):
        side = _detect_side(text)
        if side == "origin":
            charge["category"] = "EXW / Origin Charges"
            return "thc-origin-side"
        if side == "destination":
            charge["category"] = "Destination Charges"
            return "thc-destination-side"

    if quote_type == "fcl":
        if name_norm in _FCL_ORIGIN_NAMES:
            charge["category"] = "EXW / Origin Charges"
            return "fcl-origin-chargehead"
        if name_norm in _FCL_FREIGHT_NAMES and unit in _FREIGHT_UNITS:
            charge["category"] = "FCL (Ocean Freight)"
            return "fcl-freight-chargehead-and-unit"
    elif quote_type == "lcl":
        if name_norm in _LCL_FREIGHT_NAMES and unit in {"per cbm", "per ton"}:
            charge["category"] = "LCL (Ocean Freight)"
            return "lcl-freight-chargehead-and-unit"
    elif quote_type == "air":
        if name_norm.startswith("air freight"):
            charge["category"] = "AF (Air Freight)"
            return "air-freight-slab-or-base"
        if name_norm in _AIR_FREIGHT_NAMES and unit == "per kg":
            charge["category"] = "AF (Air Freight)"
            return "air-freight-surcharge-and-unit"
        if name_norm == "trucking fuel surcharge":
            charge["category"] = "EXW / Origin Charges"
            return "air-origin-trucking-fuel"
    return ""


def _detect_side(text: str) -> str:
    if any(keyword in text for keyword in _ORIGIN_KEYWORDS):
        return "origin"
    if any(keyword in text for keyword in _DESTINATION_KEYWORDS):
        return "destination"
    return ""


def _is_thc_like(name_norm: str, text: str) -> bool:
    return (
        name_norm == "thc"
        or " thc " in f" {text} "
        or "terminal handling" in text
    )


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()
