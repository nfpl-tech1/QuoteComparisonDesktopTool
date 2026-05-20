"""
Pure-Python helpers for the comparison table: unit constants and formatting functions.
No Qt imports here — safe to use from any module.
"""
import re

# ---------------------------------------------------------------------------
# Unit tables
# ---------------------------------------------------------------------------
_FLAT_UNITS = frozenset({
    "lumpsum", "per shipment", "",
    "per container (20ft)", "per container (40ft)", "per container (40ft hc)",
})

_UNIT_ABBREVS = {
    "per kg": "KG", "per cbm": "CBM", "per ton": "Ton",
    "per pallet": "Plt", "per day": "Day", "per hour": "Hr",
    "per awb": "AWB", "per hawb": "HAWB", "per bl": "BL",
    "per document": "Doc", "per set": "Set",
    "per container (20ft)": "20ft",
    "per container (40ft)": "40ft",
    "per container (40ft hc)": "40HC",
}

_UNIT_FROM_ABBREV: dict[str, str] = {
    v.lower(): k.replace("per ", "Per ") for k, v in _UNIT_ABBREVS.items()
}
_UNIT_FROM_ABBREV.update({
    "kg": "Per KG", "cbm": "Per CBM", "awb": "Per AWB",
    "hawb": "Per HAWB", "bl": "Per BL", "doc": "Per Document",
    "set": "Per Set", "ton": "Per Ton", "shipment": "Per Shipment",
})


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------
def _is_flat(unit: str) -> bool:
    return unit.lower().strip() in _FLAT_UNITS


def _unit_abbrev(unit: str) -> str:
    key = unit.lower().strip()
    if key in _UNIT_ABBREVS:
        return _UNIT_ABBREVS[key]
    return unit.replace("Per ", "").replace("per ", "").strip() or unit


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _fmt_total_usd(flat: float, variable: dict[str, float]) -> str:
    parts = []
    if flat > 0:
        parts.append(f"$ {flat:,.2f}")
    for unit, rate in sorted(variable.items()):
        rate_str = f"{rate:,.4f}".rstrip("0").rstrip(".")
        parts.append(f"$ {rate_str}/{_unit_abbrev(unit)}")
    return " + ".join(parts) if parts else "$ 0.00"


def _fmt_total_inr(flat_usd: float, variable_usd: dict[str, float],
                   inr_rate: float) -> str:
    parts = []
    if flat_usd > 0:
        parts.append(f"Rs. {flat_usd * inr_rate:,.0f}")
    for unit, rate_usd in sorted(variable_usd.items()):
        rate_inr = rate_usd * inr_rate
        rate_str = f"{rate_inr:,.2f}".rstrip("0").rstrip(".")
        parts.append(f"Rs. {rate_str}/{_unit_abbrev(unit)}")
    return " + ".join(parts) if parts else "Rs. 0"


# ---------------------------------------------------------------------------
# Cost computation helpers
# ---------------------------------------------------------------------------
def _compute_at_weight(flat: float, variable: dict[str, float], weight: float) -> float:
    """Compute actual shipment cost given chargeable weight in KG."""
    total = flat
    for unit, rate in variable.items():
        if unit.lower().strip() == "per kg":
            total += rate * weight
        else:
            total += rate  # per AWB/HAWB/BL/etc. — count as 1 per shipment
    return total


def _compute_at_cbm(flat: float, variable: dict[str, float], cbm: float) -> float:
    """Compute LCL shipment cost given chargeable CBM (W/M already applied)."""
    total = flat
    for unit, rate in variable.items():
        u = unit.lower().strip()
        if u in ("per cbm", "per ton"):
            total += rate * cbm
        else:
            total += rate
    return total


# ---------------------------------------------------------------------------
# Cell display / parsing
# ---------------------------------------------------------------------------
def _cell_display(rate: float, currency: str, unit: str) -> str:
    rate_str = f"{rate:,.4f}".rstrip("0").rstrip(".")
    unit_key = unit.lower().strip()
    if unit and unit_key not in ("lumpsum", ""):
        unit_disp = unit.replace("Per ", "/") if unit.startswith("Per ") else f"/{unit}"
        return f"{currency} {rate_str} {unit_disp}"
    return f"{currency} {rate_str}"


def _parse_cell_input(text: str, svc, fallback_currency: str = "USD") -> dict | None:
    """Parse 'SGD 3.65 /KG' or 'USD 95' into {usd_val, unit, rate, currency}."""
    text = text.strip()
    if not text or text in ("—", "-"):
        return None
    m = re.match(r'^([A-Za-z]{3})?\s*([\d,]+(?:\.\d+)?)\s*(?:/(\S+))?$', text)
    if not m:
        return None
    curr_str, rate_str, unit_abbrev_str = m.groups()
    currency = (curr_str or fallback_currency).upper()
    try:
        rate = float(rate_str.replace(",", ""))
    except ValueError:
        return None
    unit = ""
    if unit_abbrev_str:
        unit = _UNIT_FROM_ABBREV.get(unit_abbrev_str.lower(),
                                      f"Per {unit_abbrev_str.title()}")
    usd_val = svc.to_usd(rate, currency)
    return {"usd_val": usd_val, "unit": unit, "rate": rate, "currency": currency}
