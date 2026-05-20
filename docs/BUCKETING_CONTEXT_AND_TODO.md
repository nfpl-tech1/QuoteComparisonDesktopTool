# Charge Bucketing Context And To-Do

**Status:** Implemented for AIR/FCL; blocked on real LCL sample validation  
**Last Updated:** 2026-05-19  
**Purpose:** Capture the intended business rules for charge bucketing before prompt/code changes are made.

---

## Why This Exists

The current extraction flow relies heavily on prompt-driven bucketing and canonicalization.
That means business logic like "what belongs in Freight vs EXW vs Destination" needs to be
written as **broad classification guidance**, not as a tiny hard-coded charge list.

This note defines that guidance so future prompt edits stay consistent.

---

## Core Intent

### 1. Keep the context broad, not overly literal

The listed charge heads below are **examples**, not the full universe.
Different countries, carriers, ports, and forwarders use different wording for similar charges.

The model should classify charges by:

1. The business meaning of the charge
2. Whether it belongs to origin-side handling, main freight movement, or destination-side handling
3. Whether the charge behaves like a freight-rated surcharge
4. The wording around origin / destination / port / delivery context
5. Unit of measurement as a **supporting signal**, not the only signal

The model should **not** assume:

- every `/KG` charge is freight
- every `/CBM` charge is freight
- every `/Container` charge is freight
- every surcharge belongs to freight

Units help classification, but charge meaning still comes first.

---

## Mode Selection Direction

### User-selected quote mode should drive prompt selection

Instead of relying only on automatic type detection, the preferred direction is:

- the user selects whether the inquiry/quote set is `AIR`, `FCL`, or `LCL`
- that selection happens on the **first page**
- that selection is **compulsory**
- the extraction flow uses the selected mode to choose the targeted prompt

This should improve reliability because:

- prompt instructions can be tighter and more mode-specific
- the model does not have to spend effort inferring the mode first
- bucket rules can be interpreted inside the correct business context from the start
- the comparison flow becomes more predictable for the user

### Practical implication

If the user says the quotes being compared are:

- `AIR` -> use the air extraction prompt
- `FCL` -> use the FCL extraction prompt
- `LCL` -> use the LCL extraction prompt

The mode selection also drives **session persistence**: the session file for the inquiry is named
`{INQUIRY_NUMBER}-{MODE}.json` (e.g. `E260190-AIR.json`). See `INQUIRY_SESSION_PERSISTENCE_CONTEXT_AND_TODO.md`
for the full session model. Because the mode is declared up front, it is always available as part
of the session key before any files are imported or extracted.

This is especially important for the bucketing logic in this document because:

- the `FCL` rules here are more specific than the cross-mode heuristics
- some charge names overlap across modes but should be interpreted differently
- targeted prompts are safer than a one-size-fits-all inference step

### Detection still has value, but should become secondary

Auto-detection may still be useful later as:

- a soft warning
- a suggested default
- a mismatch check

But the primary business rule should be:

> the user explicitly declares whether the quote set is AIR, FCL, or LCL before extraction begins.

---

## FCL-Specific Bucketing Intent

These rules are strongest for **FCL** because that is where the current business concern is.

### EXW / Origin Charges

Charges should lean toward `EXW / Origin Charges` when they are clearly tied to:

- origin-side port activity
- booking-side administrative handling
- origin compliance / release / origin port process
- congestion or restrictions affecting the export-side move

Examples:

- Port Security
- B/L Fee
- Port Congestion
- booking-side documentation / release handling
- origin-side port filing / handling / terminal-side origin process

Important:
These examples are **not exhaustive**. Similar charge heads with different local wording should follow the same intent.

### FCL (Ocean Freight)

Charges should lean toward `FCL (Ocean Freight)` when they are clearly part of:

- the main ocean move
- freight-rated carrier surcharges
- surcharges priced as part of the line-haul / carrier freight stack
- charges that behave like freight add-ons rather than origin admin or destination handling

Examples:

- Ocean Freight
- BAF
- Fuel Surcharge
- PCS
- GRI
- EIS
- CIC
- similar freight-rated carrier surcharges

Important:
These are examples of the pattern. The intent is broader:
if a surcharge is functionally part of the freight stack, it should sit with freight.

---

## THC Rule

### THC must not default into Ocean Freight

`THC` should never be blindly treated as `Ocean Freight`.

Instead:

- `Origin THC` -> `EXW / Origin Charges`
- `Destination THC` -> `Destination Charges`

If the quote wording makes the side clear, bucket it accordingly.

Examples of origin-side signals:

- origin THC
- THC at POL
- load port THC
- export THC
- origin terminal handling

Examples of destination-side signals:

- destination THC
- THC at POD
- discharge port THC
- import THC
- destination terminal handling

If side is unclear, the model should prefer caution:

1. use nearby context from the quote
2. use port-side wording around pickup / export / import / arrival / delivery
3. avoid collapsing THC into freight just because it is often shown near ocean freight

---

## Cross-Mode Unit Heuristic

This rule applies across **AIR, FCL, and LCL**.

### Freight-style units are a positive signal, not an absolute rule

Units like these suggest a charge may belong with freight:

- `/KG`
- `/CBM`
- `/Container`
- `Per KG`
- `Per CBM`
- `Per Container`

But this does **not** mean every such charge belongs in freight.

### Intended use of the heuristic

If a charge:

1. has a freight-like unit, and
2. is freight-like in meaning,

then it should lean toward the freight bucket for that mode.

Examples:

- Ocean Freight `/CBM`
- Air Freight `/KG`
- BAF `/Container`
- Emergency Surcharge `/CBM`
- fuel-type carrier surcharge `/KG`

### Cases where unit should NOT override meaning

A charge may still belong outside freight even if it has a freight-like unit.

Examples:

- Origin THC `/Container` -> still origin if clearly origin-side
- Destination THC `/CBM` -> still destination if clearly destination-side
- Port Security `/Container` -> origin-side if that is its role in the quote
- destination CFS `/CBM` -> destination, not freight

So the rule is:

> freight-like unit strengthens a freight classification only when the charge itself is freight-like.

---

## Prompt-Design Implication

Because this system is prompt-led, the extraction prompts should be updated using:

1. broad classification principles
2. non-exhaustive examples
3. explicit counterexamples
4. side-based THC handling
5. a unit heuristic framed as a supporting signal
6. targeted prompt selection based on the user's compulsory mode choice

The prompt should avoid brittle wording like:

> "Only these exact charges go into Freight"

and instead prefer:

> "Charges functionally part of the freight stack, especially freight-rated carrier surcharges such as ..."

That keeps the model flexible across country-specific naming variation.

---

## Desired Comparison Outcome

After prompt updates, the comparison table should more naturally group:

- origin-side operational/admin/port-booking charges under `EXW / Origin Charges`
- actual line-haul freight plus freight-like carrier surcharges under the freight bucket
- import-side terminal / arrival / release / CFS / delivery charges under `Destination Charges`

This should reduce cases where:

- BAF appears outside freight
- THC is incorrectly absorbed into freight
- origin-side booking/port charges get mixed with destination handling

---

## To-Do Tracker

### Current implementation status

- [x] Added compulsory quote-mode selection on page 1
- [x] Made the selected mode visible early in the import workflow
- [x] Routed extraction by user-selected mode instead of relying only on auto-detection
- [x] Updated prompt guidance for broader FCL bucketing intent
- [x] Added prompt-level THC side rule and cross-mode unit counterexamples
- [x] Added deterministic post-extraction rebucketing for high-confidence cases
- [x] Added lightweight script-based sanity checks for rebucketing rules
- [x] Added a real-file bucketing snapshot helper for targeted regression checks
- [x] Added rebucketing audit output for QA
- [x] Added a text comparison snapshot helper for non-GUI review
- [x] Made the comparison snapshot support air slab selection via chargeable weight
- [x] Made the comparison snapshot tolerate per-file extraction failures during QA
- [x] Hardened Gemini JSON parsing against wrapped/non-clean responses
- [x] Added a malformed-JSON retry path for Gemini extraction
- [x] Added a secondary heuristic mode-mismatch warning before extraction
- [x] Added a test-data mode candidate scanner for future QA
- [x] Re-tested real AIR/FCL files and reviewed grouped comparison output
- [ ] Re-test real LCL files once suitable local samples are available

### Prompt changes

- [x] Add compulsory quote-mode selection (`AIR` / `FCL` / `LCL`) on page 1
- [x] Make prompt routing use the user-selected mode as the primary source of truth
- [x] Decide whether auto-detection remains as a warning/check instead of the main driver
- [x] Update FCL prompt bucket guidance to describe freight vs origin more broadly
- [x] Reframe listed FCL charge heads as examples, not strict enumerations
- [x] Add explicit THC rule: origin THC -> origin bucket, destination THC -> destination bucket
- [x] Add cross-mode unit heuristic as a supporting signal, not a hard rule
- [x] Add counterexamples showing freight-like units do not automatically imply freight bucket

### Example coverage

- [x] Add FCL examples where origin-side port/admin charges stay in `EXW / Origin Charges`
- [x] Add FCL examples where freight-rated surcharges stay with `FCL (Ocean Freight)`
- [x] Add THC examples for both origin and destination sides
- [x] Add LCL example showing `/CBM` does not force a charge into freight if it is clearly destination-side
- [x] Add Air example showing `/KG` supports freight classification only when the charge is actually freight-like

### Validation

- [x] Confirm user-selected mode reaches the extraction layer correctly
- [x] Confirm FCL-selected imports never accidentally use AIR or LCL prompts
- [x] Confirm LCL-selected imports never accidentally use AIR or FCL prompts
- [x] Confirm AIR-selected imports never accidentally use FCL or LCL prompts
- [x] Add lightweight sanity checks for deterministic rebucketing (`tools/test_bucketing_rules.py`)
- [x] Re-test known FCL files with real extraction snapshots (`tools/regression_bucketing_snapshot.py`)
- [x] Re-test Air files so `/KG` heuristic does not accidentally pull origin handling into `AF (Air Freight)`
- [x] Review AIR/FCL comparison output to confirm rows appear under intended buckets without manual correction
- [ ] Re-test LCL files where surcharges and THC appear in both freight and destination areas.

### Current validation notes

- Real FCL snapshot checked on `E260139 - SEA / RE E260139HoustonNhava Sheva40FTCOM.msg`
  - `B/L Fee` landed in `EXW / Origin Charges`
  - `Ocean Freight` stayed in `FCL (Ocean Freight)`
- Real FCL snapshot checked on `E250950 - SEA / Re FW E250950ShanghaiNhava sheva SEA AMS.msg`
  - `Ocean Freight` stayed in `FCL (Ocean Freight)`
- Real AIR snapshot checked on `E260141 - AIR / RE E260141SingaporeMumbaiAirUAF.msg`
  - `Pre-carriage`, `Screening Fee`, and `Trucking Fuel Surcharge` stayed in `EXW / Origin Charges`
  - `Fuel Surcharge` and air-freight slabs stayed in `AF (Air Freight)`
- Text comparison snapshot is now available via `tools/regression_compare_snapshot.py`
  - helpful for non-GUI review of grouped comparison rows
  - live extraction still shows normal model variability, so comparison-output review remains open rather than being marked complete
- Multi-vendor FCL comparison snapshot checked on `E260139 - SEA`
  - `B/L Fee`, `Port Security`, and `Port Congestion` grouped under `EXW / Origin Charges`
  - `Ocean Freight` grouped under `FCL (Ocean Freight)` across vendors
- Mixed-content validation checked on `E260190 - AIR`
  - heuristic scanner identified strong FCL candidates inside the folder
  - forcing `FCL` extraction on those files produced sensible sea-freight bucketing and comparison grouping
- AIR/FCL comparison-output review is complete for the available local snapshots
  - no additional in-repo code changes are pending from those reviewed samples
- A lightweight pre-extraction mode warning now exists in the import flow
  - it is heuristic-based and non-blocking
  - the user's selected mode still remains the source of truth
- `tools/find_mode_candidates.py` currently reports no strong LCL candidates in `Data/TestInputData`
  - LCL real-file validation therefore remains open and is blocked by sample availability

### Remaining blocker

- A real local LCL sample is still needed to finish the last open validation item.
- Until that sample exists, the remaining LCL line should be treated as blocked, not as missing implementation.

### Optional follow-up improvements

- [x] Consider adding a deterministic post-extraction rebucketing pass for high-confidence cases
- [x] Consider logging raw charge -> final bucket decisions for easier QA
- [ ] Consider documenting country/port-specific synonyms as the team encounters them

---

## Working Summary

The intended model behavior is:

- user chooses the quote mode up front
- prompt selection follows the user's compulsory mode choice
- broad, principle-based bucketing
- not rigid dependence on a small example list
- THC handled by side, never blindly as freight
- units used as supporting evidence
- charge meaning still stronger than unit pattern
