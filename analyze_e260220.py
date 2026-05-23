import json

with open("e260220_extraction.json", encoding="utf-8") as f:
    results = json.load(f)

for r in results:
    fname = r["file"]
    short = fname.split("FCL")[-1].replace(".msg", "").strip()
    print(f"\n{'='*60}")
    print(f"VENDOR: {short}")
    print(f"{'='*60}")
    if r["error"]:
        print(f"  ERROR: {r['error']}")
        continue
    for entry in r["entries"]:
        sl = entry.get("shipping_line", "")
        ct = entry.get("container_type", "")
        vn = entry.get("vendor_name", "")
        transit = entry.get("transit_days", "")
        etd = entry.get("etd", "")
        print(f"\n  [{vn}]  {sl}  {ct}  etd={etd}  transit={transit}")
        for ch in entry.get("charges_after_rebucket", []):
            cat = ch.get("category", "")
            name = ch.get("name_of_charge", "")
            rate = ch.get("rate", 0)
            curr = ch.get("currency", "")
            unit = ch.get("unit_of_measurement", "")
            remarks = ch.get("remarks", "")
            ia = " (if_applicable)" if ch.get("if_applicable") else ""
            remark_str = f"  // {remarks}" if remarks else ""
            print(f"    [{cat}]  {name}  {curr} {rate} {unit}{ia}{remark_str}")
        if entry.get("rebucket_audit"):
            print("  >> REBUCKETED:")
            for a in entry["rebucket_audit"]:
                print(f"     {a['name_of_charge']}: {a['from_category']} -> {a['to_category']} ({a['reason']})")
