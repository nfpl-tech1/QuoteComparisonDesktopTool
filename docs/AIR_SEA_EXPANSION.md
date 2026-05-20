# Quote Comparison Tool — Air, FCL & LCL Expansion Design

**Status:** Phase 4 Complete — Phase 5 (Excel/CSV export polish + end-to-end testing) Next  
**Last Updated:** 2026-05-18 (rev 5 — Phase 3 tab colour-coding + Phase 4 comparison page FCL/LCL implemented)  
**Author:** Nagarkot  

---

## Table of Contents

1. [What Exists Today](#1-what-exists-today)
2. [What Does NOT Exist (Corrections)](#2-what-does-not-exist-corrections)
3. [Scope of This Expansion](#3-scope-of-this-expansion)
4. [Design Decisions (Finalised)](#4-design-decisions-finalised)
5. [Data Model Changes](#5-data-model-changes)
6. [Charge Reference — All Three Modes](#6-charge-reference--all-three-modes)
7. [Gemini Extraction Strategy](#7-gemini-extraction-strategy)
8. [Screen-by-Screen UI/UX Design](#8-screen-by-screen-uiux-design)
9. [Implementation Phases](#9-implementation-phases)
10. [Progress Tracker](#10-progress-tracker)
11. [Open Questions Log](#11-open-questions-log)

---

## 1. What Exists Today

| Area | Status |
|---|---|
| Import `.msg` / `.pdf` / `.eml` files | ✅ Built |
| Gemini AI extraction — Air quotes only | ✅ Built |
| Thinking + Google Search enabled on Gemini 2.5 Flash | ✅ Built |
| 3 Air buckets (EXW/Origin, AF, Destination) | ✅ Built |
| Canonical charge name normalisation | ✅ Built |
| `if_applicable` optional charge flagging + confirmation dialog | ✅ Built |
| Mapping page — review / edit charges per vendor | ✅ Built |
| Comparison table — one column per vendor | ✅ Built |
| Chargeable weight KG input → live totals | ✅ Built |
| Green highlight cheapest per row | ✅ Built |
| Export CSV / Excel | ✅ Built |
| **Sub-columns per vendor (multiple shipping lines)** | ❌ Not built |
| **FCL / LCL Sea freight quotes** | ❌ Not built |
| **Auto-detect Air vs FCL vs LCL** | ❌ Not built |
| **Inquiry email filtering** | ❌ Not built |

---

## 2. What Does NOT Exist (Corrections)

> **Sub-columns:** Not implemented. Currently every vendor = one flat column.  
> This will be built in Phase 4 of this expansion.

> **Inquiry email filtering:** The email parser sends the full reply chain to Gemini,  
> including Nagarkot's original outgoing inquiry. Gemini must be explicitly instructed  
> to ignore the inquiry and extract only the vendor's response pricing.

---

## 3. Scope of This Expansion

### Included in this phase

| Mode | Pricing Unit | Notes |
|---|---|---|
| **Air** | Per KG (chargeable weight) | Already built — extend with inquiry filtering |
| **FCL** (FCL Load) | Per Container | Container type fixed by the inquiry (20ft / 40ft / 40ft HC) |
| **LCL** (Less than Container Load) | Per CBM / W-M | Very similar to Air — per-unit pricing with a chargeable volume |

### Not in this phase

- Road / Rail freight
- Multi-leg / transshipment breakdowns
- Multiple container types in one comparison (vendors quote the type you asked for)

---

## 4. Design Decisions (Finalised)

### 4.1 Quote Type Detection

**Auto-detect via Gemini, user can override on the import page.**

A lightweight pre-call classifies the document:
```
Reply with exactly one word: "air", "fcl", "lcl", or "mixed".
"mixed" means the document contains both air and sea pricing.
```
The detected type is shown as a badge next to each file. The badge is clickable so the user can correct it if needed.

---

### 4.2 Container Type — Inquiry-Defined, Extras Go to Remarks

Since Nagarkot sends a specific inquiry (e.g., "please quote 40ft GP"), the comparison table shows **only the requested container type**.

- Gemini reads the inquiry text to identify the requested container type.
- Only that container type's rates are extracted as charge rows.
- If a vendor also provides rates for other sizes (e.g., 40ft HC when 40ft GP was asked), those rates are captured in the **remarks** field of the relevant charge row — not as separate rows or sub-columns.
- The container type is shown as a label on the FCL tab toolbar for reference.
- Container types supported: `20ft GP` / `40ft GP` / `40ft HC`

---

### 4.3 LCL Chargeable Volume (W/M Rule)

LCL rates are quoted per CBM (Cubic Metre) but billed on W/M — **Weight or Measure, whichever is higher.**

Rule: `Chargeable CBM = max(Actual CBM, Gross Weight KG ÷ 1000)`

Examples:
- Cargo: 3 CBM, 2,000 KG → chargeable = max(3.0, 2.0) = **3.0 CBM** (volume wins)
- Cargo: 3 CBM, 3,500 KG → chargeable = max(3.0, 3.5) = **3.5 CBM** (weight wins)

The LCL comparison toolbar will show:
- **Volume (CBM)** input  
- **Gross Weight (KG)** input  
- **Chargeable CBM** — auto-calculated, displayed as read-only  

This mirrors exactly how the Air comparison tab shows chargeable weight.

---

### 4.4 Multiple Shipping Lines — Sub-Column Design (FCL/LCL)

When a vendor quotes multiple shipping lines (e.g., Maersk, MSC, CMA-CGM), each line becomes a **sub-column under the vendor header**.

Visual target:

```
┌─────────────────────┬───────────────────────────────┬────────────┐
│                     │         ACE Freight            │    IFF     │
│ Charge              ├──────────┬─────────┬──────────┤            │
│                     │  Maersk  │   MSC   │ CMA-CGM  │            │
├─────────────────────┼──────────┼─────────┼──────────┼────────────┤
│  Ocean Freight      │$1,200    │$1,050   │$980      │$950        │
│  BAF                │USD 200   │USD 180  │USD 200   │USD 160     │
├─────────────────────┼──────────┼─────────┼──────────┼────────────┤
│  Total USD          │$1,550    │$1,380   │$1,340    │$1,255  🟢  │
└─────────────────────┴──────────┴─────────┴──────────┴────────────┘
```

Implementation approach:
- The Qt native column header holds **shipping line names** (or vendor name for single-line vendors)
- **Row 0** of the table body is a special `vendor_header` row spec — spans all sub-columns of a given vendor, styled like a secondary header
- Vendors with only one shipping line (or Air/LCL vendors) have span = 1, no visible grouping row difference from today

---

### 4.5 Comparison Page Layout — Three Tabs

```
┌────────────────────────────────────────────────────┐
│  ✈ Air  │  📦 FCL  │  🗃 LCL                        │
└────────────────────────────────────────────────────┘
```

- Tabs only appear for modes that have loaded quotes
- If only Air quotes are loaded: no tab bar visible (same as today, zero disruption)
- Each tab is an independent comparison table with its own toolbar

---

### 4.6 Mixed Documents (Air + Sea in One File)

When Gemini detects `"mixed"`, it returns both Air and Sea charge arrays in one response.  
The app automatically creates separate VendorData entries:

- `VendorName — Air` (quote_type = `"air"`)
- `VendorName — Sea (Maersk)` (quote_type = `"fcl"`, shipping_line = `"Maersk"`)
- `VendorName — Sea (MSC)` (quote_type = `"fcl"`, shipping_line = `"MSC"`)

These appear as expandable sub-entries on the import page, indented under the source file.

---

### 4.7 Inquiry Email Filtering

Every email chain has exactly **two parties**:
- **Nagarkot Freight Forwarding Private Limited** — the buyer who sent the inquiry
- **The vendor** — who replied with their quote

Gemini must extract pricing only from the vendor's section and ignore Nagarkot's inquiry text entirely.

**Prompt instruction added to all extraction prompts:**
```
INQUIRY FILTERING:
This email chain is between Nagarkot Freight Forwarding Private Limited (the buyer)
and the vendor (whose pricing you must extract).

Ignore ALL text written by Nagarkot Freight Forwarding Private Limited.
Extract pricing ONLY from the vendor's reply.

Signs of Nagarkot's inquiry text to ignore:
  • Paragraphs starting with "Please quote", "Kindly provide", "We require",
    "Request for Quotation", "RFQ", "Dear Sir/Madam", "Dear Vendor"
  • Lines beginning with ">" or "|" (quoted reply markers)
  • Sections after "-----Original Message-----" or "From: ...@nagarkot.co.in"
  • Any section where "Nagarkot Freight Forwarding" appears as the sender
```

---

## 4.8 Real Data Analysis — Observations from Test Files

> Test files in `Data/TestInputData/` were analysed to validate design assumptions. The folder structure there is Nagarkot's own internal organisation — **users will not have this structure and will always select individual files**, exactly as the app works today.

### Confirmed: Air and Sea always arrive as separate files

ACE Freight in the E260190 inquiry sent two separate emails:
- One Air quote (to Mumbai — airport destination)
- One Sea quote (to Nhava Sheva — port destination)

This is the standard pattern. Each `.msg` or `.pdf` file = one vendor, one mode. The "mixed document" case (Air + Sea in one file) is rare but Gemini should still handle it gracefully.

### PDFs are vendor quotes — never auto-skip them

**Correction from earlier draft:** A standalone PDF in the test folder (`Nagarkot 15th May 26.pdf`) was initially assumed to be Nagarkot's inquiry document. It is actually a quote from **Bullocks FreightMasters International**. PDFs must always be treated as potential vendor quotes.

There is no reliable rule to auto-skip any file. If the user selects a file and imports it, it is processed as a vendor quote — no exceptions.

### Non-Latin vendor reply prefixes (Gemini must not misclassify)

Chinese vendors reply using Outlook's Chinese reply prefix. These are **vendor replies**, not Nagarkot's inquiry text:
- 回复 = Reply (Simplified Chinese)
- 答复 = Reply / Respond (Simplified Chinese)

The inquiry filtering prompt must explicitly note this so Gemini does not mistake Chinese-prefixed text for Nagarkot's content.

### Vendor email subject noise (no action needed)

Some vendor emails have non-standard subject prefixes. The email parser reads the body and attachments, not the subject, so these cause no issues:
- `VPCQUOTE#DZ)429 Re E260139...` — vendor's internal quote reference
- `Re EXTERNAL E260141...` — external relay marker
- `Re FW ...` — forwarded then replied

### Same vendor, different modes → different tabs

If a user imports two files from the same vendor — one Air and one Sea — they appear in separate tabs on the comparison page:
- Air tab: vendor's Air column
- FCL tab: vendor's FCL column

There is no "merge" — the two files are independent quote entries that happen to share a vendor name. The tab separation is the session separation.

This is a Phase 2 improvement, not blocking Phase 1.

---

## 5. Data Model Changes

### 5.1 `VendorData` — New Fields

```python
class VendorData:
    # Existing
    vendor_name: str
    source_file: str
    charges: list[ChargeRow]
    status: str
    error: str

    # New
    quote_type: str = "air"       # "air" | "fcl" | "lcl"
    shipping_line: str = ""       # e.g. "Maersk" — empty for Air/LCL or single-line FCL
```

`ChargeRow` itself needs no changes — same fields work for all three modes.

---

### 5.2 `constants.py` — New Bucket Sets

```python
AIR_BUCKETS = [                        # renamed from AIR_IMPORT_BUCKETS
    "EXW / Origin Charges",
    "AF (Air Freight)",
    "Destination Charges",
]

FCL_BUCKETS = [                        # NEW
    "EXW / Origin Charges",
    "FCL (Ocean Freight)",
    "Destination Charges",
]

LCL_BUCKETS = [                        # NEW
    "EXW / Origin Charges",
    "LCL (Ocean Freight)",
    "Destination Charges",
]

CONTAINER_TYPES = [                    # NEW
    "20ft GP",
    "40ft GP",
    "40ft HC",
]

QUOTE_TYPES = ["air", "fcl", "lcl"]   # NEW
```

---

### 5.3 Gemini Response Schemas

**Air (existing — add `quote_type` field):**
```json
{
  "quote_type": "air",
  "vendor_name": "ACE Freight",
  "charges": [ ... ]
}
```

**FCL — single shipping line:**
```json
{
  "quote_type": "fcl",
  "vendor_name": "ACE Freight",
  "shipping_lines": [
    {
      "shipping_line": "Maersk",
      "charges": [ ... ]
    }
  ]
}
```

**FCL — multiple shipping lines:**
```json
{
  "quote_type": "fcl",
  "vendor_name": "ACE Freight",
  "shipping_lines": [
    { "shipping_line": "Maersk",   "charges": [ ... ] },
    { "shipping_line": "MSC",      "charges": [ ... ] },
    { "shipping_line": "CMA-CGM",  "charges": [ ... ] }
  ]
}
```

**LCL:**
```json
{
  "quote_type": "lcl",
  "vendor_name": "ACE Freight",
  "charges": [ ... ]
}
```

**Mixed (Air + FCL in one document):**
```json
{
  "quote_type": "mixed",
  "vendor_name": "ACE Freight",
  "air": {
    "charges": [ ... ]
  },
  "fcl": {
    "shipping_lines": [
      { "shipping_line": "Maersk", "charges": [ ... ] }
    ]
  }
}
```

The app splits a `"mixed"` response into separate `VendorData` objects:
- One per mode (air / fcl / lcl)
- One per shipping line for FCL

---

## 6. Charge Reference — All Three Modes

### 6.1 Air (Existing — shown for reference)

| Bucket | Canonical Name | Vendor Terms |
|---|---|---|
| EXW/Origin | Pre-carriage | origin pickup, trucking, drayage |
| EXW/Origin | Airport Transfer | airport drayage, CFS-to-airport |
| EXW/Origin | Export Clearance | export customs, AES filing, EEI |
| EXW/Origin | Insurance | cargo insurance, marine insurance |
| EXW/Origin | Handling Fee | cargo handling, origin handling |
| EXW/Origin | AWB Fee | air waybill fee, AWB issuance |
| AF | Air Freight | air freight rate, air rate |
| AF | Fuel Surcharge | FSC, YQ, fuel surcharge |
| AF | Security Surcharge | SSC, YR, ISSS |
| AF | ENS Filing | ENS, entry notification |
| Destination | THC | terminal handling, destination THC |
| Destination | Delivery Order | DO fee, endorsement fee |
| Destination | Import Clearance | import customs, customs clearance |

---

### 6.2 FCL (FCL Load) — New

| Bucket | Canonical Name | Vendor Terms |
|---|---|---|
| EXW/Origin | Pre-carriage | origin pickup, trucking, inland haulage |
| EXW/Origin | Export Clearance | export customs, SB filing, shipping bill |
| EXW/Origin | CFS / Stuffing | CFS charges, stuffing, container stuffing |
| EXW/Origin | Insurance | cargo insurance, marine insurance |
| EXW/Origin | Documentation Fee | doc fee, documentation |
| FCL | Ocean Freight | OF, base rate, freight rate |
| FCL | BAF | BAF, BUC, bunker adj factor, fuel surcharge |
| FCL | CAF | CAF, currency adjustment |
| FCL | PSS | PSS, peak season surcharge |
| FCL | GRI | GRI, general rate increase |
| FCL | LSS | LSS, low sulphur surcharge |
| FCL | THC Origin | POL THC, origin terminal handling |
| FCL | B/L Fee | bill of lading, BL fee, OBL fee |
| FCL | AMS Filing | AMS, automated manifest system |
| FCL | ISF Filing | ISF, 10+2, importer security filing |
| FCL | ENS Filing | ENS, entry notification |
| FCL | Seal Fee | seal, seal charges |
| Destination | THC Destination | POD THC, destination terminal handling |
| Destination | Import Clearance | import customs, BE filing, customs clearance |
| Destination | Delivery Order | DO fee, delivery order |
| Destination | CFS / Destuffing | CFS destination, destuffing |
| Destination | Port Dues | port dues, port charges, port handling |
| Destination | Delivery | destination trucking, last-mile, inland haulage |

---

### 6.3 LCL (Less than Container Load) — New

LCL pricing is **per CBM** (or W/M), making it structurally identical to Air (per KG).  
The same comparison logic applies — just the unit is CBM instead of KG.

| Bucket | Canonical Name | Vendor Terms |
|---|---|---|
| EXW/Origin | Pre-carriage | origin pickup, trucking, collection |
| EXW/Origin | Export Clearance | export customs, SB filing |
| EXW/Origin | CFS / Stuffing | CFS origin, origin CFS, consolidation |
| EXW/Origin | Insurance | cargo insurance, marine insurance |
| EXW/Origin | Documentation Fee | doc fee, documentation |
| LCL | Ocean Freight | OF, LCL freight, ocean freight, W/M rate |
| LCL | BAF | BAF, BUC, bunker surcharge, fuel surcharge |
| LCL | CAF | CAF, currency adjustment |
| LCL | PSS | PSS, peak season surcharge |
| LCL | B/L Fee | bill of lading, BL fee, HBL fee |
| LCL | AMS Filing | AMS, automated manifest |
| LCL | ENS Filing | ENS, entry notification |
| LCL | Origin THC | POL THC, origin terminal handling |
| Destination | CFS / Destuffing | CFS destination, destination CFS, deconsolidation |
| Destination | Destination THC | POD THC, destination terminal handling |
| Destination | Import Clearance | import customs, customs clearance |
| Destination | Delivery Order | DO fee, delivery order |
| Destination | Port Dues | port dues, port charges |
| Destination | Delivery | destination trucking, last-mile delivery |

**Key LCL note:** Minimum B/L charges are very common — "USD 500 min or USD 18/CBM".  
Apply the same `min $X or $Y/unit → rate=$Y, remarks="min $X"` rule from Air.

---

## 7. Gemini Extraction Strategy

### 7.1 Two-Step Extraction

**Step 1 — Type detection (fast, cheap call):**
```
Classify this document. Reply with exactly one word:
  "air"   — Air freight quote only
  "fcl"   — Full container load (FCL) sea freight quote only
  "lcl"   — Less than container load (LCL) sea freight quote only
  "mixed" — Contains more than one of the above

Document:
{trimmed_text}
```

**Step 2 — Full extraction** using the mode-specific prompt below.

---

### 7.2 Shared Prompt Header — Inquiry Filtering

**Add this block at the top of ALL extraction prompts:**

```
INQUIRY FILTERING — CRITICAL:
This email chain is between exactly two parties:
  (a) Nagarkot Freight Forwarding Private Limited — the buyer who sent the inquiry
  (b) The vendor — who replied with their quote (this is what you must extract)

Ignore ALL text written by Nagarkot Freight Forwarding Private Limited.
Extract pricing ONLY from the vendor's reply section.

Signs of Nagarkot's inquiry text to ignore:
  • Lines beginning with ">" or "|" (quoted reply markers in chains)
  • Paragraphs starting with "Please quote", "Kindly provide", "We require",
    "Request for Quotation", "RFQ", "Dear Sir/Madam", "Dear Vendor"
  • Text after "-----Original Message-----" or "From: ...@nagarkot.co.in"
  • Any section where Nagarkot Freight Forwarding appears as the sender
```

---

### 7.3 Air Prompt (Updated)

Same as current prompt + inquiry filtering header at top.  
No other changes needed.

---

### 7.4 FCL Prompt (New)

Same structural pattern as Air:

```
ROLE          → Expert FCL freight quote extractor, 20+ years experience
INQUIRY FILTER → [see 7.2 above]
CONTAINER TYPE → Read the inquiry section to identify which container type was
                 requested (20ft GP / 40ft GP / 40ft HC). Extract rates ONLY for
                 that container type. If the vendor also provides rates for other
                 container sizes, capture them in the "remarks" field of the
                 relevant charge row (e.g. remarks="40ft HC also quoted at $1,350").
                 Return the detected container type as "container_type" in the JSON.
BUCKETS       → "EXW / Origin Charges" | "FCL (Ocean Freight)" | "Destination Charges"
CANONICAL     → FCL name normalisation table (see Section 6.2)
FEW-SHOT      →
  A. Single shipping line quote
  B. Multiple shipping lines (Maersk $1200, MSC $1050) → separate objects in shipping_lines[]
  C. BAF as % of freight vs fixed per container
  D. All-in rate vs itemised breakdown — extract itemised if both given
  E. Vendor quotes both 40ft GP and 40ft HC (inquiry asked 40ft GP only)
     → extract 40ft GP rates; put "40ft HC also quoted at $X" in remarks
  F. "Not included" charge (e.g. insurance)
  G. Optional charge (ISF, AMS)
VERIFY        → Same self-check pattern as Air
OUTPUT        → {quote_type, vendor_name, container_type, shipping_lines:[{shipping_line, charges:[]}]}
```

---

### 7.5 LCL Prompt (New)

```
ROLE          → Expert LCL freight quote extractor, 20+ years experience
INQUIRY FILTER → [see 7.2 above]
BUCKETS       → "EXW / Origin Charges" | "LCL (Ocean Freight)" | "Destination Charges"
CANONICAL     → LCL name normalisation table (see Section 6.3)
FEW-SHOT      →
  A. W/M rate: "USD 18/CBM W/M" → rate=18, unit="Per CBM", remarks="W/M applies"
  B. Min charge: "USD 500 min or USD 18/CBM" → rate=18, unit="Per CBM", remarks="min USD 500"
  C. Origin CFS + ocean freight as separate rows (don't combine)
  D. Optional charge (insurance, AMS)
  E. "Not included" charge
VERIFY        → Same self-check pattern as Air
OUTPUT        → {quote_type, vendor_name, charges:[]}
```

---

### 7.6 Mixed Document Prompt (New)

Used when Step 1 returns `"mixed"`. Single combined prompt returns both Air and Sea sections.

```
ROLE          → Expert multi-mode freight extractor
INQUIRY FILTER → [see 7.2 above]
INSTRUCTION   → This document contains both Air and Sea quotes.
                Extract both separately. For Sea, identify if FCL or LCL.
OUTPUT        → {
                  quote_type: "mixed",
                  vendor_name: "...",
                  air: { charges: [...] },
                  fcl: { shipping_lines: [...] },   ← omit if not present
                  lcl: { charges: [...] }            ← omit if not present
                }
```

---

## 8. Screen-by-Screen UI/UX Design

> **Design principle:** The user is non-technical. Every state must be self-explanatory with icons, colour, and plain language. No freight jargon in the UI (use "Air", "FCL", "LCL" — not "Air Freight", "FCL", "LCL").

---

### 8.1 Import Page

**File list with mode badges:**

```
┌───────────────────────────────────────────────────────────────────┐
│  [✈ Air]          ACE Freight.msg             ✓ Done    [✕]       │
│  [🚢 FCL]  IFF Logistics.pdf        ✓ Done    [✕]       │
│  [🗃 LCL]  Bestway LCL.msg          ✓ Done    [✕]       │
│  [✈🚢 Both]       Nagarkot Combined.msg        ✓ Done    [✕]       │
│    └─  ✈ Air       → Nagarkot — Air                               │
│    └─  🚢 Full     → Nagarkot — FCL (Maersk)           │
│    └─  🚢 Full     → Nagarkot — FCL (MSC)              │
└───────────────────────────────────────────────────────────────────┘
```

- Badge colours: ✈ Air = blue, 🚢 Full = teal, 🗃 Part = green, ✈🚢 Both = purple
- Clicking a badge opens a small popup: "Change type → Air / FCL / LCL / Both"
- Mixed-document sub-entries are indented, each has its own [✕] delete button
- Sub-entries inherit the parent vendor name with a mode suffix automatically

---

### 8.2 Mapping Page

**Tab colours by mode:**

```
┌──────────────┬──────────────────┬────────────────────┬──────────────┐
│ [✈] ACE Air  │ [🚢] ACE Maersk  │  [🚢] ACE MSC      │ [🗃] IFF LCL │
│  (blue tab)  │   (teal tab)     │    (teal tab)      │ (green tab)  │
└──────────────┴──────────────────┴────────────────────┴──────────────┘
```

- Bucket dropdown shows correct options for the tab's mode:
  - Air tabs → Air buckets
  - FCL/LCL tabs → Sea buckets
- "Optional?" column works the same across all modes
- Row height and structure identical to current Air mapping view

---

### 8.3 Comparison Page — Tab Bar

```
┌──────────────────────────────────────────────────────────────────┐
│  [✈ Air]   [📦 FCL (40ft GP)]   [🗃 LCL]   │
└──────────────────────────────────────────────────────────────────┘
```

- Container type shown in FCL tab label for clarity
- Tab bar only visible when more than one mode has data

---

### 8.4 Air Tab — Toolbar (unchanged)

```
[＋ Add Vendor]  [＋ Add Charge]       Chargeable Weight: [______ KG]
```

---

### 8.5 FCL Tab — Toolbar

```
[＋ Add Vendor]  [＋ Add Charge]       Container: [40ft GP ▾]
```

- Container type dropdown (20ft GP / 40ft GP / 40ft HC) — informational, can be changed if needed
- No weight input (FCL is per container, not per KG)

---

### 8.6 LCL Tab — Toolbar

```
[＋ Add Vendor]  [＋ Add Charge]    Volume: [___ CBM]  Weight: [___ KG]  →  Chargeable: 3.5 CBM
```

- Volume (CBM) and Gross Weight (KG) are editable
- Chargeable CBM = max(CBM, KG ÷ 1000) — auto-calculated, shown in bold, read-only
- Works identically to Air's chargeable weight for total computation

---

### 8.7 FCL Tab — Comparison Table

```
┌──────────────────────┬───────────────────────────────────┬───────────────┐
│                      │           ACE Freight             │      IFF      │
│ Charge               ├───────────┬──────────┬────────────┤               │
│                      │  Maersk   │   MSC    │  CMA-CGM   │               │
├──────────────────────┼───────────┼──────────┼────────────┼───────────────┤
│  EXW / Origin                                                             │
│    Pre-carriage      │ USD 150   │ USD 150  │ USD 150    │ USD 120  🟢   │
│    Export Clearance  │ USD 75    │ USD 75   │ USD 75     │ USD 80        │
├──────────────────────┼───────────┼──────────┼────────────┼───────────────┤
│  FCL (Ocean Freight)                                                      │
│    Ocean Freight     │$1,200 🟡  │$1,050    │$980   🟢   │$1,050         │
│    BAF               │ USD 200   │ USD 180  │ USD 200    │ USD 160  🟢   │
│    B/L Fee           │ USD 75    │ USD 75   │ USD 75     │ USD 65   🟢   │
├──────────────────────┼───────────┼──────────┼────────────┼───────────────┤
│  Destination Charges                                                      │
│    THC               │ USD 150   │ USD 150  │ USD 160    │ USD 145  🟢   │
│    Import Clearance  │ USD 120   │ USD 120  │ USD 120    │ USD 110  🟢   │
├──────────────────────┼───────────┼──────────┼────────────┼───────────────┤
│  Total USD           │$1,770     │$1,600    │$1,560      │$1,530   🟢   │
│  Total (Rs.)         │Rs.1,47,510│Rs.1,33,280│Rs.1,29,984│Rs.1,27,410 🟢│
└──────────────────────┴───────────┴──────────┴────────────┴───────────────┘
```

🟢 Lowest cost in row  |  🟡 Has remarks — hover to view

---

### 8.8 LCL Tab — Comparison Table

Identical structure to Air tab. Per-CBM rates in cells, chargeable CBM drives the totals.

```
┌──────────────────────┬─────────────────┬───────────────┐
│ Charge               │   ACE Freight   │      IFF      │
├──────────────────────┼─────────────────┼───────────────┤
│  EXW / Origin                                          │
│    Pre-carriage      │ USD 2.50/CBM    │ USD 2.00/CBM 🟢│
│    Export Clearance  │ USD 50 flat     │ USD 60 flat   │
├──────────────────────┼─────────────────┼───────────────┤
│  LCL (Ocean Freight)                                   │
│    Ocean Freight     │ USD 18/CBM   🟢 │ USD 22/CBM    │
│    BAF               │ USD 4/CBM    🟢 │ USD 5/CBM     │
│    B/L Fee           │ USD 65 flat  🟢 │ USD 75 flat   │
├──────────────────────┼─────────────────┼───────────────┤
│  Destination Charges                                   │
│    CFS / Destuffing  │ USD 5/CBM       │ USD 4/CBM  🟢 │
│    Import Clearance  │ USD 100 flat 🟢 │ USD 110 flat  │
├──────────────────────┼─────────────────┼───────────────┤
│  Total  (at 3.5 CBM) │$ 24.50+$265flat │ ...           │
│  = Total USD         │$ 351.75      🟢 │ ...           │
│  Total (Rs.)         │Rs.29,296     🟢 │ ...           │
└──────────────────────┴─────────────────┴───────────────┘
```

---

## 9. Implementation Phases

### Phase 1 — Foundation ✅ Complete

- [x] Add `quote_type`, `shipping_line`, `container_type` to `VendorData` + `uid` property
- [x] Add `FCL_BUCKETS`, `LCL_BUCKETS`, `CONTAINER_TYPES`, `QUOTE_TYPES` to `constants.py`
- [x] Keep `AIR_IMPORT_BUCKETS` as alias for `AIR_BUCKETS` (all existing references still work)
- [x] Add inquiry filtering block to Air Gemini prompt
- [x] Write FCL extraction prompt + few-shot examples (multi-shipping-line schema)
- [x] Write LCL extraction prompt + few-shot examples (W/M rule)
- [x] Mixed-document approach: pre-detect, then two separate extraction calls (air + sea)
- [x] Add pre-detection call to `GeminiService` (cheap 512-token thinking budget)
- [x] Route to correct prompt based on detected type (air / fcl / lcl / mixed)
- [x] Parse all response schemas — `_extract_air`, `_extract_fcl`, `_extract_lcl`, `_extract_sea_for_mixed`
- [x] `extract_charges` returns `list[dict]`; FCL creates one dict per shipping line
- [x] Update `import_page.py` — `file_done` signal → `Signal(str, list)`; `_extracted_paths` tracking; uid-based `app.vendors` keying; `_remove_file` cleans up by source file
- [x] Update `mapping_page.py` — `VendorMappingTable` accepts `buckets` param; `_tables` keyed by uid; correct bucket set per mode
- [x] Update `mapping_page.py` — tab labels show `[Air]` / `[FCL · Maersk]` / `[LCL]`
- [x] Update `comparison_page.py` — filters `vendors` to `quote_type == "air"` (FCL/LCL deferred to Phase 4)

### Phase 2 — Import Page ✅ Complete

- [x] Add mode badge per file after AI extraction: Air (blue) / FCL (teal) / LCL (green) / Mixed (slate) — no emojis
- [x] Make badge clickable — user can override the detected mode via inline menu
- [x] Show indented sub-entries when a single file produces multiple VendorData (multi-shipping-line FCL or mixed Air+Sea)
- [x] Allow sub-entries to be individually deleted (removes that VendorData only)
- [x] Emoji cleanup across UI — removed pseudo-emoji symbols from status badges, toolbar buttons, and warning labels

### Phase 3 — Mapping Page ✅ Complete

- [x] Colour-code tabs by mode (blue / teal / green)
- [x] Show correct bucket dropdown per mode (VendorMappingTable takes `buckets` param)
- [x] Update tab label format: `VendorName [Air]` / `VendorName [FCL · Maersk]` / `VendorName [LCL]`

### Phase 4 — Comparison Page ✅ Complete

- [x] Add Air / FCL / LCL tab bar (hidden if only one mode)
- [x] Implement `vendor_header` row spec for shipping-line sub-column grouping
- [x] Implement sub-column rendering (vendor name spans sub-columns via `setSpan`)
- [x] LCL toolbar: Volume CBM + Weight KG inputs → auto chargeable CBM (W/M rule)
- [x] `_compute_at_cbm` for LCL total calculation
- [x] `_FLAT_UNITS` extended with per-container units (FCL)
- [x] `_build_table` refactored → `_build_standard_table(vendors, buckets)` + `_build_fcl_table(vendors, buckets)`
- [x] `_update_totals` mode-aware: uses `_compute_at_weight` (Air), `_compute_at_cbm` (LCL), flat sums (FCL)
- [x] `_AddChargeDialog` mode-aware (uses correct bucket list)
- [x] `_on_rates_fetched` collects conditional charges from all modes (not just Air)
- [x] All existing features preserved: optional charges dialog, green highlight, editable cells, export

### Phase 5 — Polish & Export

- [ ] Excel export: merged vendor header cells for sub-columns
- [ ] CSV export: add `quote_type`, `shipping_line` columns
- [ ] End-to-end test: real Air, FCL, LCL, and mixed documents
- [ ] Check all edge cases: single vendor, all vendors same mode, sub-entries deleted

---

## 10. Progress Tracker

| Phase | Task | Status | Notes |
|---|---|---|---|
| **Phase 1** | `quote_type`, `shipping_line`, `container_type`, `uid` in VendorData | ✅ Done | `vendor_data.py` |
| **Phase 1** | FCL/LCL/Air buckets + CONTAINER_TYPES + QUOTE_TYPES in constants.py | ✅ Done | `AIR_IMPORT_BUCKETS` kept as alias |
| **Phase 1** | Inquiry filtering block in all extraction prompts | ✅ Done | `gemini_service.py` |
| **Phase 1** | FCL extraction prompt (multi-shipping-line schema) | ✅ Done | `gemini_service.py` |
| **Phase 1** | LCL extraction prompt (W/M rule, Per CBM) | ✅ Done | `gemini_service.py` |
| **Phase 1** | Mixed-document approach (two separate extraction calls) | ✅ Done | `_extract_sea_for_mixed` |
| **Phase 1** | Pre-detection call in GeminiService (512-token budget) | ✅ Done | `_detect_type` |
| **Phase 1** | `extract_charges` returns `list[dict]`; routes by type | ✅ Done | `gemini_service.py` |
| **Phase 1** | import_page.py — uid keying, `_extracted_paths`, list signal | ✅ Done | `import_page.py` |
| **Phase 1** | mapping_page.py — uid keys, mode bucket, tab label | ✅ Done | `mapping_page.py` |
| **Phase 1** | comparison_page.py — filter to Air vendors only | ✅ Done | Phase 4 adds FCL/LCL tabs |
| **Phase 2** | Mode badge per file after extraction (Air / FCL / LCL / Mixed) | ✅ Done | `ModeBadge` widget in `import_page.py` |
| **Phase 2** | Badge override (user correction via inline menu) | ✅ Done | `_on_mode_override` in ImportPage |
| **Phase 2** | Sub-entry rows + individual delete for multi-result files | ✅ Done | `SubEntryRow` + `_build_sub_rows` |
| **Phase 2** | Emoji cleanup across UI | ✅ Done | `import_page.py`, `comparison_page.py` |
| **Phase 3** | Tab colour coding by mode | ✅ Done | `mapping_page.py` — `setTabTextColor` |
| **Phase 3** | Correct bucket dropdown per mode | ✅ Done | Done in Phase 1 (`VendorMappingTable(buckets=...)`) |
| **Phase 3** | Tab label format with mode | ✅ Done | Done in Phase 1 (`[Air]` / `[FCL · Maersk]` / `[LCL]`) |
| **Phase 4** | Air/FCL/LCL tab bar on comparison page | ✅ Done | `_update_mode_tabs`, `_set_mode` in `comparison_page.py` |
| **Phase 4** | Vendor-header grouping row + sub-columns | ✅ Done | `_build_fcl_table` + `setSpan` |
| **Phase 4** | LCL chargeable CBM (W/M) toolbar | ✅ Done | `_lcl_inputs` frame + `_on_lcl_inputs_changed` |
| **Phase 4** | `_compute_at_cbm` helper for LCL totals | ✅ Done | Module-level function |
| **Phase 4** | Updated _build_table routing + _build_standard_table + _build_fcl_table | ✅ Done | `comparison_page.py` |
| **Phase 4** | `_update_totals` mode-aware (Air/LCL/FCL) | ✅ Done | Uses correct compute helper per mode |
| **Phase 5** | Excel export with merged vendor headers | ⏳ Pending | |
| **Phase 5** | CSV export with new fields | ⏳ Pending | |
| **Phase 5** | End-to-end testing | ⏳ Pending | |

---

## 11. Open Questions Log

| # | Question | Decision | Date |
|---|---|---|---|
| 1 | Sub-columns: merged headers or flat named columns? | **Merged headers** | 2026-05-18 |
| 2 | Air + Sea layout: tabs or one table? | **Three tabs: Air / FCL / LCL** | 2026-05-18 |
| 3 | Quote type detection: auto or manual? | **Auto + user override badge** | 2026-05-18 |
| 4 | Mixed doc split: auto or user-driven? | **Auto (Gemini returns all, app splits) — but this is a rare edge case; primary pattern is one file per vendor per mode** | 2026-05-18 |
| 5 | Container type: per-session selector or per-sub-column? | **Per-session — vendors quote what you asked for** | 2026-05-18 |
| 6 | LCL in this phase? | **Yes — same structure as Air, per CBM** | 2026-05-18 |
| 7 | Gemini prompt structure: unified or separate per mode? | **Separate (pre-detection → route to correct prompt)** | 2026-05-18 |
| 8 | Inquiry email handling | **Two-party chain (Nagarkot Freight Forwarding + Vendor) — filter by Nagarkot as sender** | 2026-05-18 |
| 9 | LCL W/M calculation | **max(CBM, KG ÷ 1000) — auto in LCL toolbar** | 2026-05-18 |
| 10 | UI terminology | **Use FCL / LCL directly — business users know these terms** | 2026-05-18 |
| 11 | Vendor quotes extra container sizes (asked 40ft GP, vendor adds 40ft HC) | **Extract requested size only; put extra sizes in remarks field** | 2026-05-18 |
| 12 | How does Gemini know which container type to extract? | **Reads inquiry section of chain to detect requested type; returns `container_type` in JSON** | 2026-05-18 |
| 13 | Should same vendor with Air + Sea files show as one session or separate? | **Separate — each file is an independent entry; the tab (Air/FCL/LCL) is the session separator** | 2026-05-18 |
| 14 | Should PDFs be auto-skipped if they look like inquiry documents? | **No — all imported files are treated as vendor quotes. The PDF in the test folder is "Bullocks FreightMasters" — not an inquiry doc.** | 2026-05-18 |
| 15 | Should there be a "Import Folder" button? | **No — users always select individual files, as today** | 2026-05-18 |

---

*Update ⏳ → ✅ in the Progress Tracker as each task is completed.*
