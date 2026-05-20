# Inquiry Session Persistence Context And To-Do

**Status:** Implemented (v1 complete)  
**Last Updated:** 2026-05-19  
**Purpose:** Capture a simple, low-cost way to save inquiry progress, reload it later, and append new vendor replies without reprocessing old files through Gemini.

---

## Why This Exists

Freight inquiries do not arrive all at once.

A typical real-world flow is:

1. Day 1: Nagarkot sends 5 RFQs
2. Day 2: only 3 vendors reply
3. The user compares those 3 quotes
4. Day 3: the remaining 2 replies arrive

With the current workflow, the user may have to start the inquiry again from scratch.
That creates two problems:

- repeated manual work
- repeated Gemini cost for files that were already parsed and extracted earlier

This note defines a **simple desktop-friendly persistence model** so one inquiry can be saved, reopened, and extended incrementally.

---

## Core Intent

The goal is not to build a heavy database system.

The goal is to:

1. treat one inquiry number as one reusable working session
2. save extracted quotes and page-2 edits
3. reload the inquiry later
4. append only newly received files
5. avoid rerunning Gemini on files that have already been processed and have not changed

The design should stay:

- simple
- local
- transparent
- easy to implement in the current codebase

---

## Recommended High-Level Model

### One inquiry + mode = one saved session file

The session key is **inquiry number + freight mode** combined, not just the inquiry number.

This is because the same inquiry number may produce separate quote sets for different modes:

- the air freight vendors may reply separately from the ocean vendors
- the extraction prompt, bucketing rules, and comparison structure differ by mode
- mapping edits and optional flags are mode-specific

Each `(inquiry, mode)` pair therefore gets its own session file.

File naming convention:

```
Data/Sessions/E260190-AIR.json
Data/Sessions/E260190-FCL.json
Data/Sessions/E260190-LCL.json
```

A single inquiry may have one, two, or all three of these files depending on which modes vendors quoted for.

That file becomes the saved working state for that inquiry + mode combination.

This aligns directly with the compulsory mode selection on page 1 described in `BUCKETING_CONTEXT_AND_TODO.md`:
since the user always declares the mode before importing, the mode is always known and can be appended to the filename at session-save time.

This is intentionally simpler than:

- a database
- a server
- a remote sync layer
- a complex cache subsystem

---

## What Should Be Saved

The session file should store enough data to reopen the inquiry without calling Gemini again for already-processed files.

### Minimum saved state

- inquiry number
- freight mode (`AIR` / `FCL` / `LCL`) — part of the session identity, not optional
- saved timestamp
- imported file records
- extracted vendor quote data
- page-2 mapping edits
- chargeable-weight / CBM-related inputs where relevant

### Why page-2 state must be saved

The saved session should preserve the **post-mapping state**, not just raw Gemini output.

That means if the user:

- changed bucket assignments
- corrected charge names
- changed optional flags
- adjusted remarks / units / rates

those edits should reopen exactly as last saved.

Otherwise, Gemini cost may be reduced, but user effort would still be lost.

---

## Suggested Session Structure

This is only a conceptual shape, not a final schema.

```json
{
  "inquiry_number": "E260190",
  "mode": "AIR",
  "saved_at": "2026-05-19T14:05:00",
  "chargeable_weight": 100.0,
  "volume_cbm": 17.5,
  "gross_weight_kg": 3.5,
  "vendors": [
    {
      "vendor_name": "Union Air Freight (Singapore) Pte Ltd",
      "source_file": "D:/Quotes/E260190/union.msg",
      "file_name": "union.msg",
      "file_size": 182344,
      "file_mtime": 1716110100.0,
      "quote_type": "air",
      "airline": "Air India (AI)",
      "shipping_line": "",
      "container_type": "",
      "etd": "",
      "transit_days": "",
      "free_days_origin": 0,
      "free_days_destination": 0,
      "charges": [
        {
          "category": "AF (Air Freight)",
          "name_of_charge": "Air Freight",
          "currency": "SGD",
          "unit_of_measurement": "Per KG",
          "rate": 4.2,
          "remarks": "min SGD105.00",
          "if_applicable": false
        }
      ]
    }
  ]
}
```

---

## Identity And Reuse Logic

To avoid rerunning Gemini unnecessarily, the app needs a lightweight way to decide whether an imported file is already known.

### Recommended simple identity

Use:

- file path
- file size
- file modified time

If those match the saved record, reuse the saved extraction.

### Why this is enough for v1

This approach is:

- cheap
- easy to implement
- readable
- good enough for a desktop workflow

It avoids the complexity of hashing in the first version.

### Optional later improvement

If needed later, a file-content hash can be added for stronger identity checking.
But it should not be required for the first implementation.

---

## Intended User Flow

### New inquiry

1. User types a new inquiry number
2. Imports files
3. Gemini extracts the pending files
4. User reviews Mapping page
5. Session is saved locally under that inquiry

### Existing inquiry reopened later

1. User selects an already-saved inquiry number
2. App loads its previous session state
3. Existing imported quotes appear immediately
4. User adds newly received files
5. Only the new files are sent to Gemini
6. Comparison updates with both old and new vendor quotes

This is the key outcome:

> old files are reused, new files are appended

---

## Suggested UI Shape

### Import page

The current inquiry number field and the mode selector together become the session entry point.

Recommended UI behavior:

- editable inquiry combo box
- user can type a new inquiry number or select a previously saved one from the dropdown
- mode selector (`AIR` / `FCL` / `LCL`) is shown alongside the inquiry number
- when both inquiry number and mode are set, the app checks if a matching session file exists

Possible actions when a saved session is found for that `(inquiry, mode)` pair:

- `Load saved session` — reopen the saved extraction + mapping state
- `Start fresh` — ignore the saved file and begin a new extraction
- `Continue current` — keep the active in-memory state without loading from disk

When a new inquiry number is typed (no matching session file exists), the app proceeds with a normal import flow.

This keeps the workflow simple and avoids adding a separate session-management screen too early.

---

## Session Behavior Principles

### 1. Inquiry number + mode is the session key

The session lookup key is the combination of inquiry number and mode: `E260190-AIR`.

Rationale: the same inquiry number can have air, FCL, and LCL sub-sessions, each with
completely different vendors, extraction results, charge structures, and mapping edits.
Treating them as one session would mix incompatible data.

The file name encodes both: `{INQUIRY}-{MODE}.json` (e.g. `E260190-FCL.json`).

### 2. Old extracted quotes should be reused

If a file is already known and unchanged, its saved extracted vendor entries should be loaded directly.

### 3. New files should be appended

If a file is new, it becomes pending extraction and is merged into the loaded inquiry state.

### 4. Changed files should be handled explicitly

If a file path matches but metadata differs, the app should not silently assume it is identical.

The app should either:

- re-extract it, or
- ask the user whether to replace the saved version

---

## Why JSON Is A Good Fit

JSON fits the current application structure well because:

- the app is local/desktop
- the session scope is naturally per inquiry
- `VendorData` already serializes cleanly enough for this style of persistence
- page 2 already works on structured charge dictionaries

This means the implementation can likely stay close to the current in-memory model instead of introducing a new storage abstraction too early.

---

## Expected Benefits

### User experience

- user does not lose inquiry progress
- user can compare partial replies now and complete replies later
- user does not have to reimport and remap everything from scratch

### Cost

- previously extracted files do not consume Gemini again
- only genuinely new or changed files need AI extraction

### Operational simplicity

- easy to inspect session files manually if needed
- easy to back up
- easy to debug

---

## Important Edge Cases

### Revised vendor quote

Sometimes a vendor sends a corrected or revised quote later.

Possible cases:

- same vendor, new file name
- same file path but modified content
- same inquiry, multiple rate options from same vendor

The session model should allow new vendor entries to be appended while still giving the user a path to replace outdated ones deliberately.

### Multiple entries from one source file

The current app already supports one file producing multiple `VendorData` entries:

- multiple airlines
- multiple shipping lines
- mixed-mode extraction

The session model must preserve that instead of assuming one file = one quote row.

### Manual edits after reload

If the user reloads an inquiry and changes bucket assignments or charge values again, the session should save the latest edited state, not revert to the original extraction.

---

## Recommended Scope For Version 1

Keep the first implementation intentionally small:

1. save one JSON file per inquiry number
2. reload session by inquiry number
3. rebuild app state from saved vendor data
4. detect new vs already-known files using path + size + modified time
5. send only new files to Gemini
6. resave the updated inquiry session after Mapping changes

This gives most of the value without overengineering.

---

## What This Is Not Trying To Solve Yet

Not in the first version:

- multi-user collaboration
- cloud sync
- cross-device session sharing
- automatic deduplication across different inquiry numbers
- full audit/version history

Those can be added later if the simple inquiry-session model proves useful.

---

## Prompt / Cost Implication

This is not mainly a prompt-engineering problem.
This is a persistence and reuse problem.

Prompt quality still matters for extraction accuracy, but the cost-saving part comes from:

- storing extracted results
- rehydrating them later
- skipping Gemini for unchanged files

---

## Desired End State

The desired behavior is:

> An inquiry can be started today, reopened tomorrow, extended next week, and compared incrementally without redoing already-processed quote files.

---

## To-Do Tracker

### Session model

- [x] Define final JSON session schema (must include `inquiry_number` + `mode` as top-level fields)
- [x] Decide folder path for saved inquiry sessions — `Data/Sessions/`
- [x] Confirm file naming: `{INQUIRY_NUMBER}-{MODE}.json` e.g. `E260190-AIR.json`
- [x] Add serialization for `VendorData` and charge rows (`VendorData.to_dict()`)
- [x] Add deserialization back into app state (`VendorData.from_dict()`)

### Import page UX

- [x] Inquiry text field with format validation (E + 6 digits)
- [x] Compulsory mode selector (`AIR` / `FCL` / `LCL`) on page 1
- [x] When inquiry + mode match a saved file, show session banner with load / start-fresh choice
- [x] Add flow for `load existing` (`_load_session`) vs `start fresh` (`_dismiss_session`)
- [x] Session banner shows vendor count and last-saved timestamp
- [ ] Convert inquiry entry into a combo box that auto-populates with saved inquiry numbers for the selected mode

### Incremental import behavior

- [x] Store file metadata (`file_size`, `file_mtime`) with each saved vendor entry
- [x] Detect already-known unchanged files (`session_service.file_is_known`)
- [x] Reuse saved extraction for unchanged files (loaded files go straight into `_extracted_paths`)
- [x] Extract only newly added files (worker only runs on `pending` = files not in `_extracted_paths`)
- [ ] Handle changed files explicitly (currently silent — re-extraction requires user to remove and re-add)

### Save lifecycle

- [x] Save when proceeding to Mapping page after all extractions complete (`_go_to_mapping`)
- [x] Save when proceeding to Comparison page (`app.go_to_comparison`)
- [ ] Save after Mapping-page edits (mapping page does not yet call `save_session`)

### Validation

- [ ] Test partial inquiry on day 1, append new files on day 2
- [ ] Confirm previously processed files do not trigger Gemini again
- [ ] Confirm Mapping edits reopen correctly
- [ ] Confirm multiple-airline and multiple-shipping-line files reload correctly

### Optional later improvements

- [ ] Add hash-based identity if path + size + mtime proves insufficient
- [ ] Add session rename / delete management
- [ ] Add simple session summary view (saved inquiry count, last updated, vendor count)
- [ ] Add lightweight version history or backup snapshots
- [ ] Save after Mapping-page edits so manual charge edits survive a restart

---

## Working Summary

The intended design is:

- one inquiry number + one mode = one saved local session file (`E260190-AIR.json`)
- the same inquiry number can have up to three separate sessions: `-AIR`, `-FCL`, `-LCL`
- JSON-based persistence in `Data/Sessions/`
- mode is a required field inside the session file and encoded in the filename
- reload and append workflow: previously extracted files are reused, new files appended
- skip Gemini for previously processed unchanged files
- preserve page-2 mapping edits so user work is not lost
- mode selection on page 1 (compulsory) is the natural trigger for session lookup

