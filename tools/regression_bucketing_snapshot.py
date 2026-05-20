"""
Run a small extraction snapshot for one or more sample files using the current
Gemini prompts plus deterministic rebucketing.

Usage:
    python tools/regression_bucketing_snapshot.py air "path\\to\\file.msg"
    python tools/regression_bucketing_snapshot.py fcl "path\\to\\file.msg"
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from src.services.bucketing_rules import rebucket_charges_with_audit
from src.services.email_parser import parse_file
from src.services.gemini_service import GeminiService


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip())
        raise SystemExit(1)

    mode = sys.argv[1].strip().lower()
    paths = [Path(p) for p in sys.argv[2:]]
    if mode not in {"air", "fcl", "lcl"}:
        raise SystemExit(f"Unsupported mode: {mode}")

    load_dotenv(dotenv_path=ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not configured")

    service = GeminiService(api_key)

    for path in paths:
        print("=" * 100)
        print(f"FILE: {path}")
        text = parse_file(str(path))
        results = service.extract_charges(text, selected_mode=mode)
        for idx, result in enumerate(results, 1):
            print("-" * 100)
            print(f"ENTRY {idx}")
            print(
                json.dumps(
                    {
                        "vendor_name": result.get("vendor_name"),
                        "quote_type": result.get("quote_type"),
                        "shipping_line": result.get("shipping_line"),
                        "airline": result.get("airline"),
                    },
                    indent=2,
                )
            )
            charges, audit = rebucket_charges_with_audit(
                result.get("quote_type"),
                result.get("charges", []),
            )
            for charge in charges:
                print(
                    f"[{charge.get('category')}] "
                    f"{charge.get('name_of_charge')} | "
                    f"{charge.get('currency')} {charge.get('rate')} | "
                    f"{charge.get('unit_of_measurement')} | "
                    f"remarks={charge.get('remarks')}"
                )
            if audit:
                print("AUDIT:")
                for item in audit:
                    print(
                        f"  - {item['name_of_charge']}: "
                        f"{item['from_category']} -> {item['to_category']} "
                        f"({item['reason']})"
                    )


if __name__ == "__main__":
    main()
