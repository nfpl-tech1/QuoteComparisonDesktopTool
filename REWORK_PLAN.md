# Quote Comparison Tool — AI Extraction Rework
## Context & Implementation Tracker

---

## What This Tool Does

PySide6 desktop app used by Nagarkot Forwarders to compare freight quotes from multiple vendors.
Users upload vendor quote files (`.msg`, `.pdf`, `.xlsx`, `.docx`), the app extracts charges via
Gemini, and displays a side-by-side comparison table.

---

## Why We Are Reworking the AI Extraction

The old approach:
1. Locally parse every file → extract everything to a single plain text string
2. Truncate to `[:12000]` chars and embed directly in the prompt
3. Send one text-only `generate_content` call per file

Problems:
- Hard 12,000 char truncation loses data on multi-vendor, multi-page quotes
- pdfplumber text extraction is lossy (misses scanned PDFs, complex table layouts)
- Excel → pipe-delimited text loses column structure
- MSG HTML body → plain text loses table structure
- Model: `gemini-2.5-flash` — more expensive than needed for extraction workloads

---

## New Architecture (Target State)

### Model
- **Primary**: `gemini-3.1-flash-lite` — cheaper, faster, purpose-built for extraction
- **Fallback**: `gemini-2.5-flash` — reserved for retry on failed/invalid output (not yet wired)

### File Decomposition Strategy

Every file is decomposed into two buckets before calling Gemini:

| Part | Source | How it reaches Gemini |
|---|---|---|
| PDF content | Direct `.pdf` upload OR PDF attachment inside `.msg` | Uploaded to File API → `Part.from_uri()` |
| Email body text + tables | `.msg` HTML body | HTML tables → JSON, rest → plain text |
| Excel data | `.xlsx` / `.xls` attachment or direct upload | openpyxl/xlrd → JSON (headers + rows per sheet) |
| Word content | `.docx` / `.doc` | python-docx/olefile → plain text |

### Why Not Upload MSG/Excel/Word to File API Directly
- **Tested**: `application/vnd.ms-outlook` uploads OK but model rejects at inference with
  `Unsupported MIME type`
- **Excel/Word**: Not in File API's supported MIME types either
- **Conclusion**: Only `application/pdf` is reliably supported. Everything else must be
  pre-processed locally.

### MSG Body Handling
- All 45 MSG files in the dataset have **both** a plain text body and an HTML body
- Plain text body discards table structure (rate tables become space-aligned blobs)
- HTML body is verbose Word HTML (42 KB for a 2.5 KB of actual content) — do NOT send raw
- **Solution**: `_html_tables_to_json()` — `<table>` elements → JSON arrays (first row = headers),
  surrounding text → plain text, document order preserved

### generate_content Call Shape
```python
contents = [
    Part.from_uri(uri=pdf1.uri, mime_type="application/pdf"),  # PDF attachment 1
    Part.from_uri(uri=pdf2.uri, mime_type="application/pdf"),  # PDF attachment 2
    "<email body text>\n\n[TABLE]\n[{...}]\n\n<more text>",   # processed body
    "[Excel: rates.xlsx]\n[{...}]",                            # excel as JSON
    "<extraction instruction prompt>",                          # the actual ask
]
```
No document text is embedded in the prompt template itself — `_build_contents()` assembles
the list. Prompts end with `"Extract all charges from the document(s) provided above."` instead
of `"DOCUMENT:\n{text[:12000]}"`.

### Parallel Processing
- **Done.** `ExtractionWorker.run()` uses `ThreadPoolExecutor(max_workers=4)`.
  All files submitted at once; results reported as each completes via Qt signals.

### New Input Field: Lane
- **Done.** `QComboBox` (Import / Export / Cross Trade) on form row 1 cols 3-5.
  Required before Proceed. Stored on `app.selected_lane`.
  Injected into all three Gemini instruction builders as `_LANE_CONTEXT_TPL`.

---

## Key Files

| File | Role |
|---|---|
| `src/services/email_parser.py` | File decomposition, HTML→JSON, Excel→JSON |
| `src/services/gemini_service.py` | File API upload, contents assembly, Gemini calls |
| `src/pages/import_page.py` | UI, ExtractionWorker thread, file list |
| `src/services/prompts.py` | All prompt templates (role, buckets, schema, examples) |
| `src/services/job_utils.py` | Inquiry number regex scan — uses `parse_file()`, NOT `decompose_file()` |
| `src/services/quote_mode_utils.py` | Mode guess for mismatch dialog — uses `parse_file()` |

**Important**: `parse_file()` in `email_parser.py` must remain unchanged. It is used by
`job_utils` and `quote_mode_utils` for lightweight local scanning (no AI). Only `decompose_file()`
is used for AI extraction.

---

## What Is Already Done

- [x] `DocumentParts` dataclass added to `email_parser.py`
- [x] `decompose_file(file_path)` — routes by file type, returns text parts + PDF bytes
- [x] `parse_excel_as_json(file_path)` — Excel workbook → JSON string (headers + rows per sheet)
- [x] `_walk_for_decompose()` — MSG attachment walker: PDFs → bytes, Excel → JSON text, Word → text
- [x] `_msg_body_for_ai()` — prefers HTML body, runs `_html_tables_to_json()`
- [x] `_html_tables_to_json()` — walks HTML in document order, tables → JSON, rest → plain text
- [x] `_table_to_json()` — converts a single BeautifulSoup `<table>` to JSON string
- [x] `_collect_parts()` — recursive HTML walker used by `_html_tables_to_json()`
- [x] `GeminiService.__init__` — default model changed to `gemini-3.1-flash-lite`
- [x] `GeminiService.extract_charges(file_path, mode)` — takes file path, not text
- [x] `GeminiService._upload_pdfs()` + `_upload_single_pdf()` — File API upload with ACTIVE polling
- [x] `GeminiService._delete_uploaded()` — cleanup after inference
- [x] `GeminiService._build_contents()` — assembles [file refs + text + instruction] list
- [x] All prompt builders (`_build_air_instruction` etc.) — return instruction only, no embedded text
- [x] `GeminiService._call()` — accepts list or string contents
- [x] `GeminiService._call_for_json()` — retry works on list contents
- [x] `ExtractionWorker.run()` — passes `path` directly to `extract_charges`, no `parse_file` call
- [x] Duplicate constant definitions removed from `prompts.py` — all five constants now defined once
- [x] Vendor-specific prompt blocks removed (`_SKYWAYS_AIR_FORMAT`, `_GALAXY_AIR_FORMAT`) — replaced by general `_AIR_RATE_NOTATION` (see note below)
- [x] `_AIR_RATE_NOTATION` added to `prompts.py` and injected into `_build_air_instruction()` (see note below)

---

## What Still Needs To Be Done

### P0 — Required Before Testing

- [x] **Remove `_detect_type` and `_detect_config`** from `gemini_service.py`
  - `_detect_type` was a fallback Gemini call (512 thinking budget) to classify Air/FCL/LCL
    when no mode was selected
  - Mode is now a **required UI field** — Proceed button is disabled until selected
  - `ExtractionWorker` always passes a valid `selected_mode` — detect path is unreachable
  - Also broken by new architecture: it takes `text: str` but `extract_charges` now takes a
    file path, so there is no text to pass it without decomposing the file twice
  - Safe to delete: `_detect_type`, `_detect_config`, and the `if qt not in (...)` branch
    in `extract_charges` — replace with a simple `qt = selected_mode` assignment

- [x] **Verify `thinking_budget` compatibility with `gemini-3.1-flash-lite`**
  - Removed `thinking_config` entirely from `_extract_config`; Flash-Lite does not support thinking
  - `_extract_config = types.GenerateContentConfig()` — model default settings

- [ ] **End-to-end smoke test** — run the app against one MSG file from each inquiry folder,
  confirm charges are extracted correctly with the new file-based flow
  - Test files to use: `Data/TestInputData/E260173/RE E260173 Thailand IndiaAirTRA.msg`
    (has rate table in body), and one FCL file from `E260139 - SEA/`

### P1 — Core Feature Additions

- [x] **Lane field in import UI** (`src/pages/import_page.py`)
  - `QComboBox` with `Import` / `Export` / `Cross Trade` added to form row 1 cols 3-5
    (same visual row as Chargeable Weight — mirrors Mode alignment above it)
  - `app.selected_lane` initialized in `src/app.py`; restored in `_restore_initial_state`
  - Required before Proceed; lane combo disabled during extraction, re-enabled after

- [x] **Lane in GeminiService** (`src/services/gemini_service.py`)
  - `selected_lane` added to `extract_charges(file_path, selected_mode, selected_lane)`
  - `_build_lane_context(lane)` helper renders `_LANE_CONTEXT_TPL` with per-lane detail text
  - Lane context injected after `_INQUIRY_FILTER` in all three instruction builders
  - `_LANE_CONTEXT_TPL` and `_LANE_DETAILS` added to `prompts.py`

- [x] **Parallel file processing** (`src/pages/import_page.py`)
  - `ExtractionWorker.run()` now uses `ThreadPoolExecutor(max_workers=4)`
  - All files submitted at once; `file_started` emitted before submit, results via `as_completed`
  - `all_done` emitted after executor context exits

### P2 — Quality / Robustness

- [x] **Fallback to `gemini-2.5-flash`** on invalid JSON output after retry
  - Flow: attempt 1 (primary) → attempt 2 (primary + retry msg) → attempt 3 (`_FALLBACK_MODEL`)
  - If all three fail, `json.JSONDecodeError` propagates to caller

- [x] **File API cleanup on exception** — verified: `_delete_uploaded` is in `finally` block
  - If `decompose_file` raises: no PDFs uploaded yet — no cleanup needed, exception propagates
  - `_upload_pdfs` catches all failures internally, always returns a list — cannot raise itself
  - `try/finally` correctly wraps all extraction calls — cleanup fires on any inference error

- [x] **Excel JSON size guard** — `_EXCEL_MAX_ROWS = 500` added to `parse_excel_as_json`
  - Rows beyond limit are skipped; a `"note"` key added to the sheet entry when truncated
  - Applies to both openpyxl (`.xlsx`/`.xlsm`) and xlrd (`.xls`) paths

### P3 — Cleanup

- [x] **Delete test/inspection scripts** — `test_msg_upload.py`, `inspect_msg.py`,
  `scan_msg_bodies.py` removed from repo root

- [N/A] **Update UI subtitle text** — still accurate, no change needed

- [N/A] **Settings/config** — model is already configurable via the Settings page UI
  (`self.settings.get("gemini_model", "")` in `app.py`). The hardcoded default in
  `GeminiService.__init__` is a last-resort fallback only.

---

## Prompt Rework (Use Prompt Engineering Skill)

### Current Prompt Anatomy

Every extraction prompt is assembled from named constants in `src/services/prompts.py`
and composed inside `GeminiService._build_*_instruction()`. The structure is:

```
AIR:
[ROLE]            _AIR_ROLE
[INQUIRY_FILTER]  _INQUIRY_FILTER   (shared)
[RATE_NOTATION]   _AIR_RATE_NOTATION — compact C/G weight basis + /min column guide (AIR only)
[BUCKETS]         _AIR_BUCKETS
[CANONICAL]       _AIR_CANONICAL
[EXAMPLES]        _AIR_EXAMPLES
[VERIFY]          _VERIFY            (shared)
[JSON_SCHEMA]     _AIR_JSON_SCHEMA
"Extract all charges from the document(s) provided above."

FCL:
[ROLE] [INQUIRY_FILTER] [CONTAINER_SEL] [BUCKETS] [CANONICAL] [EXAMPLES] [VERIFY] [JSON_SCHEMA]

LCL:
[ROLE] [INQUIRY_FILTER] [BUCKETS] [CANONICAL] [EXAMPLES] [VERIFY] [JSON_SCHEMA]
```

No vendor-specific overrides remain. The `_AIR_RATE_NOTATION` block covers the compact
cell format used by Skyways (and potentially other vendors).

### Known Issue: Duplicate Definitions in prompts.py

Several constants are defined **twice** — the second definition silently overrides the first.
Python uses the last definition, so the first is dead code.

| Constant | First def (lines) | Second def (lines) | What changed |
|---|---|---|---|
| `_AIR_EXAMPLES` | 107–180 (box-drawing art) | 483–533 (plain text + Example H added) | Example H added, formatting simplified |
| `_FCL_EXAMPLES` | 297–341 (box-drawing art) | 535–588 (plain text + B,C,D,G,H added) | Many examples added |
| `_LCL_BUCKETS` | 392–407 | 591–609 | IMPORTANT `/CBM` note added |
| `_LCL_CANONICAL` | 409–425 | 611–627 | No change (exact duplicate) |
| `_LCL_EXAMPLES` | 427–448 | 629–652 | Example D added |

~~**Action required**: Delete the first (dead) definitions for all five constants.~~ **Done.**

### What Is Already Done (Prompt Side)

- [x] Prompt builders no longer embed `{text[:12000]}` — document comes via `_build_contents()`
- [x] All instructions end with `"Extract all charges from the document(s) provided above."`
- [x] `_DETECT_PROMPT_TPL` deleted (mode is now required UI input)
- [x] Duplicate definitions cleaned up — all five constants now defined exactly once
- [x] `_SKYWAYS_AIR_FORMAT` and `_GALAXY_AIR_FORMAT` removed — replaced by `_AIR_RATE_NOTATION` (see note below)
- [x] `_AIR_RATE_NOTATION` injected into `_build_air_instruction()` immediately after `[INQUIRY_FILTER]`

### What Still Needs To Be Done (Prompt Side)

#### [DONE] Lane context block

`_LANE_CONTEXT_TPL` and `_LANE_DETAILS` added to `prompts.py`.
Injected after `_INQUIRY_FILTER` in all three instruction builders via `_build_lane_context()`.

#### [DONE] Document format acknowledgment

`_INQUIRY_FILTER` now contains a `DOCUMENT FORMAT:` block explaining `[TABLE]`, `[Excel: filename]`,
plain text, and uploaded PDF parts.

#### [N/A] Vendor-specific format updates

`_SKYWAYS_AIR_FORMAT` and `_GALAXY_AIR_FORMAT` have been **removed entirely** rather than
updated. The compact rate notation they described (C/G weight basis, `/min` minimums) is now
covered generically by `_AIR_RATE_NOTATION` in every air prompt. Galaxy's Excel-specific
column mapping (`DISC RATE` vs `FREIGHT RATE`) is **not yet covered** — if Galaxy accuracy
suffers, consider adding an Example I to `_AIR_EXAMPLES` showing the `DISC RATE` pattern.

### Domain Knowledge Reference (For AI Agents Writing/Editing Prompts)

This section explains the freight forwarding context so an AI agent can make correct
prompt decisions without domain expertise.

#### The Three Modes

| Mode | What it is | Key unit | Typical charge count |
|---|---|---|---|
| AIR | Air freight | Per KG (weight slabs) | 6–15 charges |
| FCL | Full Container Load sea freight | Per Container | 5–12 charges |
| LCL | Less than Container Load (groupage) | Per CBM or W/M | 4–10 charges |

#### The Three Charge Buckets (all modes have these, named differently)

| Bucket | What it covers | Examples |
|---|---|---|
| EXW / Origin Charges | Everything at origin before the main leg | Pickup, export customs, screening, origin handling, AWB fee |
| Main Freight | The carrier's core charge for moving cargo | Air freight rate, ocean freight, fuel surcharge, security surcharge |
| Destination Charges | Everything at destination after the main leg | THC, import customs, delivery order, last-mile delivery |

**Critical rules that must stay in all prompts:**
- `if_applicable=true` ONLY for explicitly conditional charges ("if required", "subject to approval")
- Minimums go in `remarks`, never as the `rate`
- Pre-calculated totals (e.g. "Total: $937.60") are NOT extracted — only per-unit rates
- When a vendor quotes multiple carriers/airlines, each gets its own entry with ALL shared charges duplicated

#### What "Lane" Changes in Practice

| Lane | Origin | Destination | Which bucket Nagarkot pays for |
|---|---|---|---|
| Import | Foreign | India | Destination Charges (India side) |
| Export | India | Foreign | EXW / Origin Charges (India side) |
| Cross Trade | Foreign | Foreign | All three equally |

Lane does NOT change which charges to extract — extract everything the vendor quotes.
Lane context helps Gemini correctly classify ambiguous charges (e.g. "THC" — origin or
destination? — is clearer when the model knows which end is India).

#### Weight Slabs (Air Only)

Air rates are quoted in weight break slabs. The naming convention is strict:
- `-45` = rate for shipments under 45 kg → `"Air Freight -45"`
- `+45K` = rate for 45 kg and above → `"Air Freight +45K"`
- `+100K`, `+250K`, `+300K`, `+500K`, `+1000K` follow the same pattern
- Each slab is a separate charge row in the JSON

#### Vendor-Specific Formats

Two vendors have proprietary formats requiring special prompt treatment:
- **Skyways Group**: pipe/space-delimited rate table in email body; cell values encode
  weight basis (C=chargeable, G=gross) and minimum in a compact notation like `"31C/500"`
- **Galaxy Freight**: Excel attachment with columns including a `DISC RATE` (discounted,
  the real price) and `FREIGHT RATE` (rack rate, ignore)

---

## Data Facts (From Scanning the Test Dataset)

- 45 `.msg` files scanned
- **100%** have both plain text body AND HTML body
- **100%** have `<table>` elements in the HTML body
- 0 plain-text-only files — safe to always use `_msg_body_for_ai()` with HTML path
- File sizes range from ~50 KB to ~500 KB
- Most MSG files have 8–18 attachments (mostly images/signatures, some PDFs)

---

## Constraints & Decisions Already Made

| Decision | Rationale |
|---|---|
| Keep `parse_file()` unchanged | Used by `job_utils` and `quote_mode_utils` for local scanning — must not require File API |
| Don't upload MSG/Excel/Word to File API | Tested: MSG rejected at inference; Excel/Word not in supported MIME types |
| HTML body → not sent raw | 42 KB Word HTML for 2.5 KB of content — 95% noise, wastes tokens |
| Tables → JSON not pipe-delimited | Pipe-delimited is ambiguous; JSON preserves header-value mapping |
| `google_search` tool removed from extract config | Not needed for document extraction; adds cost and latency |
| Thinking config removed | `gemini-3.1-flash-lite` does not support `ThinkingConfig`; `_extract_config = types.GenerateContentConfig()` |
| Vendor-specific prompts removed, not updated | User decision: replace `_SKYWAYS_AIR_FORMAT` + `_GALAXY_AIR_FORMAT` with general `_AIR_RATE_NOTATION`. Galaxy's `DISC RATE` column is NOT yet covered — monitor accuracy. |
| `/number` minimum only in `/min` columns | User clarified: cell value `25C/75` means min=75 ONLY when the column header contains `/min` (e.g. "FSC/min"). In plain columns the slash is NOT a minimum encoding. |
