"""Re-apply the updated bucketing rules to the saved extraction and show diff."""
import json
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.services.bucketing_rules import rebucket_charges_with_audit

with open("e260220_extraction.json", encoding="utf-8") as f:
    results = json.load(f)

for r in results:
    fname = r["file"]
    short = fname.split("FCL")[-1].replace(".msg", "").strip()
    print(f"\n{'='*70}")
    print(f"FILE: {short}")
    print(f"{'='*70}")
    if r["error"]:
        print(f"ERROR: {r['error']}")
        continue

    for entry in r["entries"]:
        sl = entry.get("shipping_line", "-")
        ct = entry.get("container_type", "-")
        print(f"\n  Carrier: {sl}  |  Container: {ct}")

        raw_charges = entry.get("charges", [])
        fixed, audit = rebucket_charges_with_audit(entry.get("quote_type", "fcl"), raw_charges)

        print(f"  {'CHARGE NAME':<35} {'CATEGORY (FIXED)':<30} {'RATE':>10}  CCY")
        print(f"  {'-'*35} {'-'*30} {'-'*10}  ---")
        for ch in fixed:
            name = ch.get("name_of_charge", "")
            cat  = ch.get("category", "")
            rate = ch.get("rate", 0)
            ccy  = ch.get("currency", "")
            ia   = " (if_applicable)" if ch.get("if_applicable") else ""
            print(f"  {name:<35} {cat:<30} {rate:>10.2f}  {ccy}{ia}")

        if audit:
            print(f"  [REBUCKETED]")
            for a in audit:
                print(f"    {a['name_of_charge']}: {a['from_category']} -> {a['to_category']} ({a['reason']})")
        else:
            print(f"  [no rebucketing needed]")
