"""Print the exact JSON structure Gemini returned for each E260220 file."""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

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

    # Reconstruct the raw Gemini JSON (shipping_lines with raw charges, before rebucketing)
    gemini_json = {
        "vendor_name": r["entries"][0]["vendor_name"] if r["entries"] else "",
        "shipping_lines": []
    }
    for entry in r["entries"]:
        gemini_json["shipping_lines"].append({
            "shipping_line":         entry.get("shipping_line", ""),
            "container_type":        entry.get("container_type", ""),
            "etd":                   entry.get("etd", ""),
            "transit_days":          entry.get("transit_days", ""),
            "free_days_origin":      entry.get("free_days_origin", 0),
            "free_days_destination": entry.get("free_days_destination", 0),
            "charges":               entry.get("charges", []),
        })

    print(json.dumps(gemini_json, indent=2, ensure_ascii=False))
