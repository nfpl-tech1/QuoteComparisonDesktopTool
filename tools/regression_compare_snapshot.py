"""
Build a simple text comparison snapshot for a few files using the current
extraction and rebucketing flow.

Usage:
    .\\venv\\Scripts\\python tools/regression_compare_snapshot.py air "file1.msg" "file2.msg"
    .\\venv\\Scripts\\python tools/regression_compare_snapshot.py air --weight 100 "file1.msg" "file2.msg"
"""

import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from src.services.bucketing_rules import rebucket_charges
from src.services.email_parser import parse_file
from src.services.gemini_service import GeminiService


def main():
    if len(sys.argv) < 4:
        print(__doc__.strip())
        raise SystemExit(1)

    mode = sys.argv[1].strip().lower()
    weight_kg = 0.0
    raw_args = sys.argv[2:]
    files: list[Path] = []
    i = 0
    while i < len(raw_args):
        token = raw_args[i]
        if token == "--weight":
            weight_kg = float(raw_args[i + 1])
            i += 2
            continue
        files.append(Path(token))
        i += 1
    if mode not in {"air", "fcl", "lcl"}:
        raise SystemExit(f"Unsupported mode: {mode}")

    load_dotenv(dotenv_path=ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not configured")

    service = GeminiService(api_key)
    vendors: list[dict] = []
    for path in files:
        print(f"PROCESSING: {path}")
        try:
            text = parse_file(str(path))
            results = service.extract_charges(text, selected_mode=mode)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue
        for result in results:
            charges = rebucket_charges(result.get("quote_type"), result.get("charges", []))
            if result.get("quote_type") == "air" and weight_kg > 0:
                from src.models.vendor_data import VendorData
                from src.services.slab_utils import auto_mark_slab_optional

                vd = VendorData(result.get("vendor_name") or "Unknown Vendor", str(path))
                vd.quote_type = "air"
                vd.set_charges_from_dicts(charges)
                auto_mark_slab_optional(vd, weight_kg)
                charges = vd.to_charge_dicts()

            vendors.append({
                "label": _vendor_label(result),
                "charges": charges,
            })

    if not vendors:
        raise SystemExit("No vendors could be extracted for this snapshot.")

    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for vendor in vendors:
        seen = defaultdict(set)
        for charge in vendor["charges"]:
            if charge.get("if_applicable"):
                continue
            bucket = charge.get("category") or ""
            name = (charge.get("name_of_charge") or "").strip()
            key = name.lower()
            if bucket and key and key not in seen[bucket]:
                grouped[bucket].append((key, name))
                seen[bucket].add(key)

    print("=" * 120)
    print("VENDORS:")
    for vendor in vendors:
        print(f" - {vendor['label']}")

    for bucket, names in grouped.items():
        print("=" * 120)
        print(bucket)
        deduped = []
        used = set()
        for key, name in names:
            if (bucket, key) not in used:
                deduped.append((key, name))
                used.add((bucket, key))
        for key, name in deduped:
            print(f"  {name}")
            for vendor in vendors:
                match = next(
                    (
                        ch for ch in vendor["charges"]
                        if (ch.get("category") or "") == bucket
                        and (ch.get("name_of_charge") or "").strip().lower() == key
                        and not ch.get("if_applicable")
                    ),
                    None,
                )
                if match:
                    print(
                        f"    {vendor['label']}: "
                        f"{match.get('currency')} {match.get('rate')} | "
                        f"{match.get('unit_of_measurement')}"
                    )
                else:
                    print(f"    {vendor['label']}: —")


def _vendor_label(result: dict) -> str:
    vendor = result.get("vendor_name") or "Unknown Vendor"
    airline = (result.get("airline") or "").strip()
    shipping_line = (result.get("shipping_line") or "").strip()
    if airline:
        return f"{vendor} [{airline}]"
    if shipping_line:
        return f"{vendor} [{shipping_line}]"
    return vendor


if __name__ == "__main__":
    main()
