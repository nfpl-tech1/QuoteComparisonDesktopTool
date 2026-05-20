"""
Air freight weight-slab detection and auto-marking of non-applicable slabs.

After marking, the applicable slab's name_of_charge is normalised to
"Air Freight" so it aligns in the comparison table with vendors that
quoted a single flat per-KG rate (no slabs).

Standard IATA weight breaks: 45, 100, 250, 300, 500, 1000 kg.
Charge names produced by Gemini follow the pattern:
  "Air Freight -45"    → slab for shipments < 45 kg
  "Air Freight +45K"   → slab for shipments ≥ 45 kg (up to next break)
  "Air Freight +100K"  → slab for shipments ≥ 100 kg
  etc.
"""
import re


def _detect_weight_slab(name: str) -> int | None:
    """
    Return the weight threshold encoded in a charge name, or None if not a slab.
    Positive value → '≥ X kg' slab  (e.g. 'Air Freight +45K'  → 45).
    Negative value → '< X kg' slab  (e.g. 'Air Freight -45'   → -45).
    """
    clean = name.strip()
    m = re.search(r'\+\s*(\d+)\s*[kK]', clean)
    if m:
        return int(m.group(1))
    m = re.search(r'[-<]\s*(\d+)\s*[kK]?(?:\s|$)', clean)
    if m:
        return -int(m.group(1))
    return None


def auto_mark_slab_optional(vd, weight_kg: float) -> None:
    """
    For an air-freight VendorData that contains weight-slab charges:

    1. Mark non-applicable slabs as if_applicable=True (hidden from comparison).
    2. Rename the applicable slab to "Air Freight" so it lines up in the same
       comparison row as vendors that quoted a plain per-KG rate with no slabs.

    Edge cases handled:
    - Vendor with only one slab (e.g. +45K only) and weight ≥ 45: the single
      slab is applicable and gets renamed — aligns with flat-rate vendors.
    - Vendor with only one slab that does NOT apply (e.g. Air India -45 when
      weight=100 KG): charge is marked optional → shows "—" in the comparison.
      This is correct: the rate explicitly doesn't cover the shipment weight.
    - Vendor with a flat "Air Freight" rate (no slab pattern): function is a
      no-op because no slab charges are detected.
    """
    if vd.quote_type != "air" or weight_kg <= 0:
        return

    tagged = [
        (ch, _detect_weight_slab(ch.name_of_charge))
        for ch in vd.charges
    ]
    slab_charges = [(ch, s) for ch, s in tagged if s is not None]

    if not slab_charges:
        return  # no slab patterns — flat-rate vendor, nothing to do

    ge_breaks = sorted({s for _, s in slab_charges if s > 0})

    def _is_applicable(slab: int) -> bool:
        if slab < 0:                            # "< X kg" slab
            return weight_kg < abs(slab)
        idx = ge_breaks.index(slab)
        upper = ge_breaks[idx + 1] if idx + 1 < len(ge_breaks) else float("inf")
        return ge_breaks[idx] <= weight_kg < upper

    for ch, slab in slab_charges:
        if _is_applicable(slab):
            ch.if_applicable = False
            ch.name_of_charge = "Air Freight"   # normalise to flat-rate name
        else:
            ch.if_applicable = True
