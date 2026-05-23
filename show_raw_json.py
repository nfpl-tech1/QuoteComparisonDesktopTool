"""Print the raw JSON the model returns for each E260220 file, before bucketing."""
import json

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
        sl = entry.get("shipping_line", "—")
        ct = entry.get("container_type", "—")
        print(f"\n  Carrier: {sl}  |  Container: {ct}")
        print(f"  {'CHARGE NAME':<35} {'CATEGORY':<30} {'RATE':>10}  {'CCY':<4} UNIT")
        print(f"  {'-'*35} {'-'*30} {'-'*10}  {'-'*4} {'-'*25}")
        for ch in entry.get("charges", []):
            name = ch.get("name_of_charge", "")
            cat  = ch.get("category", "")
            rate = ch.get("rate", 0)
            ccy  = ch.get("currency", "")
            unit = ch.get("unit_of_measurement", "")
            ia   = " *" if ch.get("if_applicable") else ""
            print(f"  {name:<35} {cat:<30} {rate:>10.2f}  {ccy:<4} {unit}{ia}")
        if entry.get("rebucket_audit"):
            print(f"\n  [REBUCKET AUDIT]")
            for a in entry["rebucket_audit"]:
                print(f"    {a['name_of_charge']}: {a['from_category']} -> {a['to_category']} ({a['reason']})")
