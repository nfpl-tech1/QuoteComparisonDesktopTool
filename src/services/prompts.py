"""
All Gemini prompt string constants — no imports needed.
"""

# ---------------------------------------------------------------------------
# Shared: inquiry filter + document format context (added to every prompt)
# ---------------------------------------------------------------------------
_INQUIRY_FILTER = """\
CONTEXT — TWO PARTIES IN THIS DOCUMENT:
  1. Nagarkot Freight Forwarding Private Limited (the BUYER / us)
     → IGNORE their text entirely.
  2. The VENDOR / carrier
     → EXTRACT only their quoted charges.

Ignore text that reads like an inquiry ("please quote for…", "kindly advise",
"we need rates for…"). Chinese reply prefixes 回复/答复 mark VENDOR replies —
do extract those. Never assign the buyer's company as the vendor_name.

DOCUMENT FORMAT:
The content provided may include any combination of:
  - Plain email text (paragraphs, headers, signatures)
  - [TABLE] blocks — HTML rate tables from the email body converted to JSON arrays;
    the first object in each array contains the column headers
  - [Excel: filename] blocks — Excel attachments converted to JSON arrays
  - Uploaded PDF pages (rendered before this text block)
All content is from the same vendor quote set.\
"""

# ---------------------------------------------------------------------------
# Shared: pre-return verification checklist
# ---------------------------------------------------------------------------
_VERIFY = """\
BEFORE returning JSON — run this checklist:
  Step 1 — Vendor: confirm vendor_name is the freight forwarder or carrier,
    not the shipper/consignee. Use "Unknown Vendor" if genuinely absent.
  Step 2 — Carriers: confirm you have one airlines / shipping_lines entry
    per distinct carrier or airline quoted in the document.
  Step 3 — Each charge row:
    ✓ category is copied exactly from one of the 3 bucket strings
    ✓ rate is a plain number — minimum / floor belongs in remarks
    ✓ if_applicable=true ONLY when source uses explicit conditional language:
      "optional", "if applicable", "if required", "subject to approval"
    ✓ no row added for a pre-calculated total — only per-unit rates
  Step 4 — Output: return the JSON object only, no preamble, no explanation.\
"""


# ---------------------------------------------------------------------------
# Shared: lane / shipment direction context (injected after _INQUIRY_FILTER)
# ---------------------------------------------------------------------------
_LANE_CONTEXT_TPL = """\
SHIPMENT DIRECTION: {lane}
{lane_detail}\
"""

_LANE_DETAILS = {
    "import": (
        "Cargo is moving INTO India (import). "
        "Destination-side charges (import customs clearance, destination delivery, "
        "destination THC/ATC) are the primary cost focus. "
        "When a charge references India-side delivery or customs, classify as Destination Charges."
    ),
    "export": (
        "Cargo is moving OUT OF India (export). "
        "Origin-side charges (pre-carriage, export clearance, origin handling) are the primary cost focus. "
        "When a charge references pick-up from shipper or export customs, classify as EXW / Origin Charges."
    ),
    "cross trade": (
        "This is a CROSS TRADE shipment — both origin AND destination are outside India. "
        "Nagarkot acts as an intermediary arranger. "
        "Classify origin-side charges as EXW / Origin Charges and destination-side charges "
        "as Destination Charges in the normal way."
    ),
}


# ===========================================================================
# AIR FREIGHT
# ===========================================================================

_AIR_ROLE = """\
You are an expert air freight rate extractor with 20+ years of experience in
international freight forwarding. Your sole output is structured JSON.

The two most common errors in air freight extraction — avoid them:
  1. Miscategorising a charge as "AF (Air Freight)" solely because its unit is /KG.
     Origin trucking and trucking fuel surcharges are "EXW / Origin Charges" even
     when charged per-KG.
  2. Putting a minimum floor in the rate field. The per-unit rate goes in rate;
     the floor goes in remarks.\
"""

_AIR_RATE_NOTATION = """\
COMPACT RATE NOTATION — some vendors encode rates in a compact cell format.
Parse these cells as follows:

  Weight basis suffix (attached to the number):
    C  = Chargeable Weight  (default — assume C when no suffix is given)
    G  = Gross Weight

  Minimum suffix — CONTEXT-DEPENDENT on the column header:
    A slash followed by a number (e.g. "/75") encodes a minimum charge ONLY when
    the column header itself contains "/min" or "/MIN"
    (e.g. "FSC/min", "CTG/min", "SSC/min").
    In columns whose header does NOT have "/min", ignore any slash-number in the
    cell or treat the entire cell as a plain rate.

  Examples in a "/min" column (e.g. column header = "FSC/min"):
    "25C"       -> rate=25,    unit="Per KG"
    "25G"       -> rate=25,    unit="Per KG", remarks="per gross weight"
    "25C/75"    -> rate=25,    unit="Per KG", remarks="min 75"
    "25G/75"    -> rate=25,    unit="Per KG", remarks="min 75; per gross weight"
    "3.14C/330" -> rate=3.14,  unit="Per KG", remarks="min 330"

  Examples in a plain column (header has no "/min"):
    "300"       -> rate=300,   unit="Per KG"
    "25C"       -> rate=25,    unit="Per KG"
    "600/AWB"   -> rate=600,   unit="Per AWB"  (flat per air waybill — not a min)

  GROSS vs CHARGEABLE WEIGHT:
    For EXPORT shipments vendors may quote different rates on gross weight (G) and
    chargeable weight (C). Extract both as separate rows when both appear.
    For IMPORT shipments chargeable weight (C) is the standard; extract gross
    weight rows if present and note in remarks.\
"""

_AIR_BUCKETS = """\
CHARGE BUCKETS — assign every charge to exactly one of these 3 categories.
Copy the quoted string exactly into the "category" field.

  "EXW / Origin Charges"
      Origin pickup / pre-carriage / trucking from shipper's door,
      airport transfer (origin side), export customs clearance,
      AES / EEI / ENS / PLACI filings, packing / crating / labelling,
      screening or x-ray at origin, cargo handling fees at origin,
      cargo insurance (if quoted), AWB issuance fee.
      UNIT NOTE: a /KG unit does NOT move a charge into the AF bucket —
      origin trucking fuel surcharges are /KG and still belong here.

  "AF (Air Freight)"
      Air freight rate / rate slab, fuel surcharge (FSC / YQ),
      security surcharge (SSC / YR), in-flight screening,
      CASS fees, airline-levied surcharges, bunker surcharges.
      Only airline-levied charges belong here. Do NOT place origin
      trucking, origin handling, or origin fuel surcharges in this bucket.

  "Destination Charges"
      Airline terminal charge (ATC) at destination, destination THC,
      import customs clearance, delivery order (DO) / airline DO fee,
      endorsement fee, manifest charges, destination trucking / last-mile,
      bonded warehouse fees.\
"""

_AIR_CANONICAL = """\
CANONICAL CHARGE NAMES — map vendor terms to these exact labels:

  "Pre-carriage"             <- origin pickup, trucking, local trucking, pre-carriage,
                                collection, drayage, origin haulage
  "Airport Transfer"         <- airport transfer, airport drayage, CFS-to-airport,
                                origin airport handling
  "Export Clearance"         <- export clearance, export customs, AES filing,
                                EEI filing, automated export system
  "Insurance"                <- cargo insurance, air cargo insurance, CIF insurance
  "Air Freight"              <- air freight, total air freight, air rate
                                (single rate, no weight break)
  "Air Freight -45"          <- slab for shipments < 45 kg
  "Air Freight +45K"         <- slab for shipments >= 45 kg
  "Air Freight +100K"        <- slab for shipments >= 100 kg
  "Air Freight +250K"        <- slab for shipments >= 250 kg
  "Air Freight +300K"        <- slab for shipments >= 300 kg
  "Air Freight +500K"        <- slab for shipments >= 500 kg
  "Air Freight +1000K"       <- slab for shipments >= 1000 kg
                                (use this "+XK" / "-X" pattern for any slab)
  "Fuel Surcharge"           <- FSC, YQ, airline fuel surcharge, fuel levy
                                → "AF (Air Freight)" bucket ONLY
  "Trucking Fuel Surcharge"  <- fuel surcharge on trucking / pre-carriage, TFS,
                                local fuel surcharge, fuel on local delivery
                                → "EXW / Origin Charges" bucket ONLY
  "Security Surcharge"       <- SSC, YR, security surcharge, ISSS
  "AWB Fee"                  <- AWB fee, air waybill fee, AWB issuance
  "ENS Filing"               <- ENS, Entry Notification System filing
  "Handling Fee"             <- handling, cargo handling, origin handling
  "Documentation Fee"        <- documentation, doc fee
  "Airline Terminal Charge"  <- ATC, airline terminal charge, airport terminal charge
  "THC"                      <- terminal handling charge, destination handling charge
  "Delivery Order"           <- delivery order, DO fee, airline DO, endorsement fee
  "Import Clearance"         <- import customs, import clearance, customs clearance (dest)\
"""

_AIR_EXAMPLES = """\
FEW-SHOT EXAMPLES:

Example A: "Min $X or $Y/kg" — minimum vs per-unit rate
  Source: "Airport Transfer: Min $85.00 or $0.25 per kg"
  Reasoning: "$0.25 per kg" is the per-unit rate; "$85.00" is the floor applied when
    the calculated total falls below it. Per-unit rate goes in rate; floor goes in remarks.
  Extract: name="Airport Transfer", rate=0.25, unit="Per KG", remarks="min $85.00"
  WRONG: rate=85.00  (that is the minimum floor, not the charge per-KG)

Example B: Combined line — split into separate rows
  Source: "Air Freight: $4.60/kg + ENS $35.00/awb"
  Reasoning: Two distinct charges joined by "+". Each becomes its own row.
    ENS (Entry Notification System) is an export filing fee — it is an origin charge
    even though it appears alongside an airline charge.
  Row1: category="AF (Air Freight)", name="Air Freight", rate=4.60, unit="Per KG"
  Row2: category="EXW / Origin Charges", name="ENS Filing", rate=35, unit="Per AWB"

Example C: Insurance with formula
  Source: "Insurance - $75 min or $0.50 per $100 CIV value + freight"
  Reasoning: $75 is the minimum; the formula is variable. Use the minimum as the rate
    with Lumpsum unit; put the formula in remarks. Insurance is typically conditional.
  Extract: name="Insurance", rate=75, unit="Lumpsum", if_applicable=true,
    remarks="min $75; or $0.50 per $100 CIV + freight"

Example D: Charge explicitly excluded
  Source: "Cargo Insurance not included unless specifically quoted."
  Reasoning: The charge is absent from this quote but should still appear in the output
    so the comparison table shows the exclusion clearly. Rate=0, if_applicable=false
    (the charge is not offered, not just conditional).
  Extract: name="Insurance", rate=0, remarks="Not included in this quote", if_applicable=false

Example E: Pre-calculated total — skip the total, keep the rate
  Source: "Total Trucking Per Kg $1.20 | Total Trucking $937.60"
  Reasoning: $1.20/kg is the per-unit rate. $937.60 is the pre-calculated total for a
    specific shipment weight. Only per-unit rates belong in the output — totals vary by
    weight and would distort cross-vendor comparisons.
  Extract: name="Pre-carriage", rate=1.20, unit="Per KG"
  WRONG: adding a second row with rate=937.60

Example F: Multiple airlines in same email
  Source:
    "On AI General to BOM (Daily direct)
     -45kg: SGD10.75/kg or MIN SGD105.00  FSC: SGD0.11/kg
     On 6E General to BOM (Daily direct)
     +45kg: SGD4.20/kg  FSC: SGD0.15/kg"
  Reasoning: Two distinct airline sections, each with different rates. Each becomes a
    separate object in "airlines". Any charges stated before the airline sections (AWB
    fee, screening, origin handling, etc.) apply to ALL airlines and must be duplicated
    into every entry — the comparison system reads each entry as a standalone quote.
  airlines[0]: airline_name="Air India (AI)",
    charges: [Air Freight -45: rate=10.75 remarks="min SGD 105.00", Fuel Surcharge: rate=0.11]
  airlines[1]: airline_name="IndiGo (6E)",
    charges: [Air Freight +45K: rate=4.20, Fuel Surcharge: rate=0.15]

Example G: Weight-slab rate table
  Source:
    "Airfreight rate (/kg.)
     Dest  Carrier  MIN    -45   +45K  +100K  +250K  +500K  +1000K  Fuel
     BOM   EK       50.00  5.00  2.48  2.14   1.80   1.63   1.63    2.07"
  Reasoning: Each weight column is a separate pricing tier — each becomes its own row.
    The MIN column (50.00) is the minimum per-AWB amount that applies to all slabs;
    put it in remarks of every slab row, do NOT create a separate MIN row.
    Fuel (2.07/kg) is a "Fuel Surcharge" row.
  Row1: name="Air Freight -45",    rate=5.00, unit="Per KG", remarks="min USD 50.00"
  Row2: name="Air Freight +45K",   rate=2.48, unit="Per KG", remarks="min USD 50.00"
  Row3: name="Air Freight +100K",  rate=2.14, unit="Per KG", remarks="min USD 50.00"
  Row4: name="Air Freight +250K",  rate=1.80, unit="Per KG", remarks="min USD 50.00"
  Row5: name="Air Freight +500K",  rate=1.63, unit="Per KG", remarks="min USD 50.00"
  Row6: name="Air Freight +1000K", rate=1.63, unit="Per KG", remarks="min USD 50.00"
  Row7: name="Fuel Surcharge",     rate=2.07, unit="Per KG"

Example H: /KG unit does not determine bucket
  Source: "Origin Trucking Fuel Surcharge SGD 0.20/kg"
  Reasoning: The charge name says "Origin Trucking" — this is a fuel levy on ground
    transport, not airline freight. The /KG unit is simply the billing basis for
    trucking. Category follows the charge's nature and side, not its unit.
  Extract: category="EXW / Origin Charges", name="Trucking Fuel Surcharge",
    rate=0.20, unit="Per KG"
  WRONG: category="AF (Air Freight)" — a /KG unit does not make a charge airline freight.\
"""

_AIR_JSON_SCHEMA = """\
Return ONLY valid JSON — no markdown fences, no explanations, no extra text:

{
  "vendor_name": "<freight forwarder / carrier company name — NOT shipper or consignee>",
  "airlines": [
    {
      "airline_name": "<airline name + IATA code e.g. 'Air India (AI)', 'Emirates (EK)'; empty string if not specified>",
      "transit_days": "<transit time e.g. '3-5 days', or empty string>",
      "charges": [
        {
          "category": "<exact bucket string — one of the 3 defined above>",
          "name_of_charge": "<canonical label or short description, 2-5 words>",
          "currency": "<3-letter ISO code e.g. USD / EUR / SGD / INR / AED>",
          "unit_of_measurement": "<Per KG / Per Shipment / Per AWB / Per HAWB / Lumpsum / Per CBM / Per Set / Per Document / Per BL>",
          "rate": <numeric — plain number, no currency symbols or commas>,
          "remarks": "<minimum amounts, conditions, weight-basis notes — empty string if none>",
          "if_applicable": <true if charge is explicitly conditional/optional, otherwise false>
        }
      ]
    }
  ]
}

OUTPUT RULES:
  • One entry per airline; shared charges duplicated into every entry
  • If no airline is specified, use one entry with airline_name=""
  • Omit rows where rate=0 AND remarks="" AND if_applicable=false
  • Default currency to USD when ambiguous
  • Split combined lines ("X $A + Y $B") into separate rows\
"""


# ===========================================================================
# FCL (Full Container Load)
# ===========================================================================

_FCL_ROLE = """\
You are an expert FCL (Full Container Load) sea freight rate extractor with
20+ years of experience in international freight forwarding. Your sole output
is structured JSON.

The two most common errors in FCL extraction — avoid them:
  1. Placing THC in the "FCL (Ocean Freight)" bucket. THC belongs to whichever
     side of the journey it occurs on: origin THC → EXW, destination THC →
     Destination Charges.
  2. Using the /Container unit as a cue to assign a charge to the freight bucket.
     Origin THC and origin handling are charged /container and still belong to
     "EXW / Origin Charges".\
"""

_FCL_BUCKETS = """\
CHARGE BUCKETS — assign every charge to exactly one of these 3 categories.
Copy the quoted string exactly into the "category" field.

  "EXW / Origin Charges"
      Origin trucking to port, export customs clearance, VGM fee, origin CFS /
      container freight station, container stuffing / packing, cargo insurance,
      origin documentation, origin-side port handling, booking / release / filing
      admin, export-side security charges, origin THC, origin-side congestion or
      restriction charges (port security, B/L / OBL / telex release handling,
      export terminal handling, and similar origin-side operational charges).
      UNIT NOTE: a /Container or /BL unit does NOT move a charge here from freight.

  "FCL (Ocean Freight)"
      Ocean freight base rate (FAK), BAF / bunker adjustment, CAF / currency
      adjustment, PSS / peak season surcharge, GRI / general rate increase,
      CIC / equipment imbalance, PCS / congestion surcharge, EIS / emergency
      surcharges, and carrier line-haul add-ons that function as part of the
      freight stack.
      IMPORTANT: do NOT place THC here by default — THC is always side-based.

  "Destination Charges"
      Destination THC, import customs clearance, delivery order / release fee,
      destination trucking / inland haulage, customs examination / scanning fee,
      endorsement fee.\
"""

_FCL_CANONICAL = """\
CANONICAL CHARGE NAMES — map vendor terms to these exact labels:

  "Pre-carriage"         <- origin trucking, haulage to port, local trucking
  "Export Clearance"     <- export customs, export clearance, AES filing
  "VGM Fee"              <- VGM, verified gross mass, SOLAS VGM
  "Origin CFS"           <- CFS (origin), container freight station, stuffing fee
  "Insurance"            <- cargo insurance, marine insurance
  "Port Security"        <- port security, port safety fee, export security fee
  "Ocean Freight"        <- ocean freight, sea freight, base freight, FAK rate
  "BAF"                  <- BAF, bunker adjustment, fuel surcharge, IFO, LSS, EBS, EFF
  "PSS"                  <- PSS, peak season surcharge, high season surcharge
  "GRI"                  <- GRI, general rate increase
  "CAF"                  <- CAF, currency adjustment factor
  "CIC"                  <- CIC, container imbalance charge, equipment imbalance
  "PCS"                  <- PCS, peak congestion surcharge, premium carrier surcharge
  "Emergency Surcharge"  <- EES, EIS, emergency surcharge, war surcharge
  "Port Congestion"      <- port congestion, congestion surcharge, congestion levy
  "B/L Fee"              <- B/L fee, bill of lading, OBL fee, documentation release
  "Telex Release Fee"    <- telex release, surrender fee, release fee
  "Documentation Fee"    <- doc fee, documentation, carrier documentation
  "THC"                  <- THC, terminal handling charge, terminal handling
  "Import Clearance"     <- import customs, import clearance, customs clearance
  "Delivery Order"       <- delivery order, DO fee, release fee, endorsement
  "Destination Trucking" <- destination trucking, inland delivery, last mile\
"""

_FCL_CONTAINER_SELECTION = """\
CONTAINER TYPE SELECTION — CRITICAL:
  1. Find the INQUIRY section at the bottom of the email chain (written by
     Nagarkot Freight Forwarding Private Limited). Look for "No. & Type of Containers".
  2. Map inquiry language to container_type and unit:
       "1x20ft" / "1*20ft" / "20' GP"           -> container_type="20ft GP",  unit="Per Container (20ft)"
       "1x40ft" / "1*40ft" / "40' GP"           -> container_type="40ft GP",  unit="Per Container (40ft)"
       "1x40HC" / "1*40HC" / "40' HC" / "40HQ" -> container_type="40ft HC", unit="Per Container (40ft HC)"
  3. When the vendor shows a TABLE with columns for multiple sizes (20GP | 40GP | 40HQ),
     read ONLY the column that matches the requested type. Ignore all other columns.
  4. Set container_type to the REQUESTED size — not the vendor's full list.\
"""

_FCL_EXAMPLES = """\
FEW-SHOT EXAMPLES:

Example A: Basic FCL quote — THC is destination, not freight
  Source: "Maersk 40ft GP: Ocean Freight $850 + BAF $120 + Dest THC $165"
  Reasoning: BAF is a carrier freight surcharge -> "FCL (Ocean Freight)". Destination THC
    is terminal handling at the arrival port -> "Destination Charges". THC is NEVER ocean
    freight — its bucket is always determined by which side of the journey it occurs on.
  shipping_line="Maersk", container_type="40ft GP"
  Row1: category="FCL (Ocean Freight)", name="Ocean Freight", rate=850, unit="Per Container (40ft)"
  Row2: category="FCL (Ocean Freight)", name="BAF",           rate=120, unit="Per Container (40ft)"
  Row3: category="Destination Charges", name="THC",           rate=165, unit="Per Container (40ft)"

Example B: Origin admin charges — stay in EXW even when listed with freight
  Source: "Ocean Freight USD 2035/40HC + B/L fee USD 15/bl + Port Security USD 12/container"
  Reasoning: B/L fee is origin-side export documentation -> "EXW / Origin Charges". Port
    Security is an origin-side levy -> "EXW / Origin Charges". Neither belongs in the
    freight bucket despite appearing in the same line.
  Row1: category="FCL (Ocean Freight)", name="Ocean Freight", rate=2035, unit="Per Container (40ft HC)"
  Row2: category="EXW / Origin Charges", name="B/L Fee",     rate=15,   unit="Per BL"
  Row3: category="EXW / Origin Charges", name="Port Security", rate=12,  unit="Per Container (40ft HC)"

Example C: THC ambiguity — side determines bucket
  Source: "Origin THC USD 110/40HC + Destination THC USD 165/40HC + GRI USD 95/40HC"
  Reasoning: "Origin THC" is export-side terminal handling -> "EXW / Origin Charges".
    "Destination THC" is import-side -> "Destination Charges". GRI is a carrier-side rate
    increase added to the freight stack -> "FCL (Ocean Freight)".
  Row1: category="EXW / Origin Charges", name="THC", rate=110, unit="Per Container (40ft HC)"
  Row2: category="Destination Charges",  name="THC", rate=165, unit="Per Container (40ft HC)"
  Row3: category="FCL (Ocean Freight)",  name="GRI", rate=95,  unit="Per Container (40ft HC)"

Example D: /Container unit does not determine bucket
  Source: "EIS USD 85/container + BAF USD 120/container + Origin THC USD 35/container"
  Reasoning: EIS and BAF are carrier line-haul surcharges -> "FCL (Ocean Freight)". Origin
    THC is origin terminal handling — the /container unit does not move it into freight.
    The charge's nature and side determine the bucket, not the unit.
  Row1: category="FCL (Ocean Freight)",  name="Emergency Surcharge", rate=85,  unit="Per Container (40ft)"
  Row2: category="FCL (Ocean Freight)",  name="BAF",                 rate=120, unit="Per Container (40ft)"
  Row3: category="EXW / Origin Charges", name="THC",                 rate=35,  unit="Per Container (40ft)"
  WRONG: putting Origin THC in "FCL (Ocean Freight)" because it is charged /container.

Example E: Multiple shipping lines — one entry per carrier
  Source: "CMA-CGM 40GP: $920 | Evergreen 40GP: $880 | COSCO 40GP: $860"
  Reasoning: Each carrier has its own quoted rate. Three separate objects in "shipping_lines",
    each with its own shipping_line and charges. Non-carrier charges (THC, customs, etc.)
    stated once in the email must be duplicated into every carrier entry.
  [0] shipping_line="CMA CGM",  Ocean Freight rate=920
  [1] shipping_line="Evergreen", Ocean Freight rate=880
  [2] shipping_line="COSCO",     Ocean Freight rate=860

Example F: Size mentioned but not priced — no extra entry
  Source: "40ft GP: $850; 40ft HC available on request"
  Reasoning: Only 40ft GP has a firm rate. 40ft HC is mentioned but unpriced — create no
    separate entry for it. Note the availability in remarks on the Ocean Freight row.
  container_type="40ft GP"
  Row1: name="Ocean Freight", rate=850, unit="Per Container (40ft)",
    remarks="40ft HC available on request"
  WRONG: creating a second shipping_line entry with empty or 0 rates for 40ft HC.

Example G: Unit selection reference
  20ft container  -> unit="Per Container (20ft)"
  40ft GP         -> unit="Per Container (40ft)"
  40ft HC / HQ    -> unit="Per Container (40ft HC)"
  Per B/L charge  -> unit="Per BL"

Example H: Multi-column rate table — read only the requested column
  Inquiry: "No. & Type of Containers: 1*20ft"
  Vendor table:
    Carrier  ETD         20GP  40GP  40HQ  Free days
    KMTC     2026-03-24  1420  1290  1290  14
  Reasoning: The inquiry requests 20ft GP. When the vendor shows multiple container
    columns, extract ONLY the column matching the requested size. The 40GP / 40HQ
    columns are irrelevant to this comparison.
  shipping_line="KMTC", container_type="20ft GP", etd="2026-03-24", free_days_destination=14
  Ocean Freight rate=1420  (the 20GP column)
  WRONG: rate=1290 — that is the 40GP/40HQ price, not the requested 20ft rate.\
"""

_FCL_JSON_SCHEMA = """\
Return ONLY valid JSON — no markdown fences, no explanations, no extra text:

{
  "vendor_name": "<freight forwarder / carrier company name>",
  "shipping_lines": [
    {
      "shipping_line": "<carrier name e.g. Maersk, KMTC — empty string if not specified>",
      "container_type": "<REQUESTED container type from inquiry e.g. 20ft GP, 40ft GP, 40ft HC>",
      "etd": "<Estimated Time of Departure as a date string e.g. 2026-03-24, or empty string>",
      "transit_days": "<transit time e.g. '21 days', 'direct / 21 days', or empty string>",
      "free_days_origin": <integer free days at origin port, 0 if not mentioned>,
      "free_days_destination": <integer free days at destination port, 0 if not mentioned>,
      "charges": [
        {
          "category": "<exact bucket string — one of the 3 defined above>",
          "name_of_charge": "<canonical label or short description, 2-5 words>",
          "currency": "<3-letter ISO code>",
          "unit_of_measurement": "<Per Container (20ft) / Per Container (40ft) / Per Container (40ft HC) / Per BL / Per Shipment / Lumpsum>",
          "rate": <numeric rate for the REQUESTED container type — plain number, no symbols>,
          "remarks": "<minimums, conditions — empty string if none>",
          "if_applicable": <true if explicitly conditional/optional, otherwise false>
        }
      ]
    }
  ]
}

OUTPUT RULES:
  • One entry per distinct carrier / rate option
  • container_type = the REQUESTED size from the inquiry
  • When vendor shows a multi-column table, extract ONLY the requested column
  • Omit rows where rate=0 AND remarks="" AND if_applicable=false
  • Default currency to USD when ambiguous\
"""


# ===========================================================================
# LCL (Less than Container Load)
# ===========================================================================

_LCL_ROLE = """\
You are an expert LCL (Less than Container Load / groupage) sea freight rate
extractor with 20+ years of experience. LCL rates are typically quoted per CBM
or on a W/M basis (weight-or-measure: charge whichever of 1 CBM or 1,000 KG
produces a higher value). Your sole output is structured JSON.

The most common error in LCL extraction — avoid it:
  Categorising THC or destination CFS as "LCL (Ocean Freight)" because the unit
  is /CBM. The unit does not determine the bucket — the charge's side (origin vs
  destination) does.\
"""

_LCL_BUCKETS = """\
CHARGE BUCKETS — assign every charge to exactly one of these 3 categories.
Copy the quoted string exactly into the "category" field.

  "EXW / Origin Charges"
      Origin trucking, export customs clearance, origin CFS / receiving charge,
      cargo insurance, origin documentation, origin-side terminal handling.

  "LCL (Ocean Freight)"
      LCL ocean freight rate per CBM or W/M, BAF per CBM, carrier documentation
      tied to the line-haul, and freight-like carrier surcharges that function
      as part of the freight stack.
      IMPORTANT: /CBM or /Ton unit does NOT move THC or destination CFS here —
      the charge's side determines the bucket, not the unit.

  "Destination Charges"
      Destination CFS / unstuffing / deconsolidation, import customs clearance,
      delivery order fee, destination THC, destination trucking / last mile.\
"""

_LCL_CANONICAL = """\
CANONICAL CHARGE NAMES — map vendor terms to these exact labels:

  "Pre-carriage"        <- origin trucking, collection, pre-carriage
  "Export Clearance"    <- export customs, export clearance
  "Origin CFS"          <- origin CFS, receiving charge, stuffing, CFS handling
  "Insurance"           <- cargo insurance, marine insurance
  "Ocean Freight"       <- ocean freight, LCL freight, groupage freight, sea freight
  "BAF"                 <- BAF, bunker adjustment, fuel surcharge (sea)
  "B/L Fee"             <- B/L fee, HAWB fee, bill of lading, doc release fee
  "Emergency Surcharge" <- EES, EIS, congestion surcharge, emergency levy
  "Documentation Fee"   <- doc fee, documentation
  "Destination CFS"     <- destination CFS, CFS delivery, unstuffing, deconsolidation
  "THC"                 <- THC, terminal handling, terminal handling charge
  "Import Clearance"    <- import customs, customs clearance
  "Delivery Order"      <- delivery order, DO fee\
"""

_LCL_EXAMPLES = """\
FEW-SHOT EXAMPLES:

Example A: Standard LCL quote
  Source: "LCL freight: USD 18/CBM, BAF USD 5/CBM, B/L USD 45"
  Reasoning: Ocean freight and BAF are carrier line-haul charges -> "LCL (Ocean Freight)".
    B/L fee is carrier documentation tied to the line-haul -> also "LCL (Ocean Freight)".
  Row1: category="LCL (Ocean Freight)", name="Ocean Freight", rate=18, unit="Per CBM"
  Row2: category="LCL (Ocean Freight)", name="BAF",           rate=5,  unit="Per CBM"
  Row3: category="LCL (Ocean Freight)", name="B/L Fee",       rate=45, unit="Per BL"

Example B: W/M rate
  Source: "Ocean freight USD 22 W/M"
  Reasoning: W/M (Weight-or-Measure) means the carrier charges on whichever of weight
    (per metric ton) or volume (per CBM) produces a higher value for the shipment.
    Use "Per CBM" as the canonical unit and note the W/M basis in remarks.
  Extract: name="Ocean Freight", rate=22, unit="Per CBM",
    remarks="W/M basis (1 CBM = 1,000 KG)"

Example C: Per-ton and per-CBM quoted separately for same W/M rate
  Source: "Freight: $20/cbm or $20/ton (W/M)"
  Reasoning: Same rate expressed for both CBM and ton — this is a single W/M rate, not
    two separate charges. One row with "Per CBM" and the W/M note in remarks.
  Extract: name="Ocean Freight", rate=20, unit="Per CBM",
    remarks="W/M: per CBM or per Ton, whichever greater"

Example D: /CBM unit does not determine bucket
  Source: "Destination THC USD 12/cbm + Destination CFS USD 18/cbm"
  Reasoning: Both charges are destination-side. The /CBM unit is merely the billing
    basis — it does not pull these charges into the LCL freight bucket. The charge's
    side of the journey determines the bucket.
  Row1: category="Destination Charges", name="THC",             rate=12, unit="Per CBM"
  Row2: category="Destination Charges", name="Destination CFS", rate=18, unit="Per CBM"
  WRONG: category="LCL (Ocean Freight)" because the unit is /CBM.\
"""

_LCL_JSON_SCHEMA = """\
Return ONLY valid JSON — no markdown fences, no explanations, no extra text:

{
  "vendor_name": "<freight forwarder / carrier company name>",
  "etd": "<Estimated Time of Departure e.g. 2026-03-24, or empty string>",
  "transit_days": "<transit time e.g. '28 days', 'approx 30 days', or empty string>",
  "free_days_origin": <integer free days at origin port, 0 if not mentioned>,
  "free_days_destination": <integer free days at destination port, 0 if not mentioned>,
  "charges": [
    {
      "category": "<exact bucket string — one of the 3 defined above>",
      "name_of_charge": "<canonical label or short description, 2-5 words>",
      "currency": "<3-letter ISO code>",
      "unit_of_measurement": "<Per CBM / Per Ton / Per BL / Per Shipment / Lumpsum>",
      "rate": <numeric — plain number, no symbols>,
      "remarks": "<minimums, W/M notes, conditions — empty string if none>",
      "if_applicable": <true if explicitly conditional/optional, otherwise false>
    }
  ]
}

OUTPUT RULES:
  • Omit rows where rate=0 AND remarks="" AND if_applicable=false
  • Default currency to USD when ambiguous
  • W/M rates: use unit="Per CBM" and put W/M rule in remarks\
"""
