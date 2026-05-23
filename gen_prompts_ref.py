import sys
sys.path.insert(0, ".")

from src.services.prompts import (
    _INQUIRY_FILTER, _VERIFY,
    _LANE_IMPORT, _LANE_EXPORT, _LANE_CROSSTRADE,
    _AIR_ROLE, _AIR_RATE_NOTATION, _AIR_BUCKETS, _AIR_CANONICAL,
    _AIR_COMMON_EXAMPLES, _AIR_IMPORT_EXAMPLES, _AIR_EXPORT_EXAMPLES, _AIR_CROSSTRADE_EXAMPLES,
    _AIR_JSON_SCHEMA,
    _FCL_ROLE, _FCL_CONTAINER_SELECTION, _FCL_BUCKETS, _FCL_CANONICAL,
    _FCL_COMMON_EXAMPLES, _FCL_IMPORT_EXAMPLES, _FCL_EXPORT_EXAMPLES, _FCL_CROSSTRADE_EXAMPLES,
    _FCL_JSON_SCHEMA,
    _LCL_ROLE, _LCL_BUCKETS, _LCL_CANONICAL,
    _LCL_COMMON_EXAMPLES, _LCL_IMPORT_EXAMPLES, _LCL_EXPORT_EXAMPLES, _LCL_CROSSTRADE_EXAMPLES,
    _LCL_JSON_SCHEMA,
)

SEP = "─" * 77

SHARED_BLOCKS = [
    ("_INQUIRY_FILTER", _INQUIRY_FILTER, "Shared — injected into every prompt"),
    ("_VERIFY",         _VERIFY,         "Shared — pre-return checklist, every prompt"),
]

LANE_BLOCKS = [
    ("_LANE_IMPORT",      _LANE_IMPORT,      "Lane — Import"),
    ("_LANE_EXPORT",      _LANE_EXPORT,      "Lane — Export"),
    ("_LANE_CROSSTRADE",  _LANE_CROSSTRADE,  "Lane — Cross Trade"),
]

AIR_MODE_BLOCKS = [
    ("_AIR_ROLE",          _AIR_ROLE,          "AIR — role + top-level error warnings"),
    ("_AIR_RATE_NOTATION", _AIR_RATE_NOTATION, "AIR — compact rate notation (C/G, /min columns)"),
    ("_AIR_BUCKETS",       _AIR_BUCKETS,       "AIR — EXW / AF / Destination bucket definitions"),
    ("_AIR_CANONICAL",     _AIR_CANONICAL,     "AIR — canonical charge name mappings"),
    ("_AIR_JSON_SCHEMA",   _AIR_JSON_SCHEMA,   "AIR — output JSON schema + output rules"),
]

FCL_MODE_BLOCKS = [
    ("_FCL_ROLE",                _FCL_ROLE,                "FCL — role + top-level error warnings"),
    ("_FCL_CONTAINER_SELECTION", _FCL_CONTAINER_SELECTION, "FCL — container type selection rules"),
    ("_FCL_BUCKETS",             _FCL_BUCKETS,             "FCL — EXW / Ocean / Destination bucket definitions"),
    ("_FCL_CANONICAL",           _FCL_CANONICAL,           "FCL — canonical charge name mappings"),
    ("_FCL_JSON_SCHEMA",         _FCL_JSON_SCHEMA,         "FCL — output JSON schema + output rules"),
]

LCL_MODE_BLOCKS = [
    ("_LCL_ROLE",        _LCL_ROLE,        "LCL — role + top-level error warning"),
    ("_LCL_BUCKETS",     _LCL_BUCKETS,     "LCL — EXW / Ocean / Destination bucket definitions"),
    ("_LCL_CANONICAL",   _LCL_CANONICAL,   "LCL — canonical charge name mappings"),
    ("_LCL_JSON_SCHEMA", _LCL_JSON_SCHEMA, "LCL — output JSON schema + output rules"),
]

COMBO_BLOCKS = [
    ("_AIR_COMMON_EXAMPLES",     _AIR_COMMON_EXAMPLES,     "AIR — common examples (all lanes)"),
    ("_AIR_IMPORT_EXAMPLES",     _AIR_IMPORT_EXAMPLES,     "AIR + Import — combination-specific notes/examples"),
    ("_AIR_EXPORT_EXAMPLES",     _AIR_EXPORT_EXAMPLES,     "AIR + Export — combination-specific notes/examples"),
    ("_AIR_CROSSTRADE_EXAMPLES", _AIR_CROSSTRADE_EXAMPLES, "AIR + Cross Trade — combination-specific notes/examples"),
    ("_FCL_COMMON_EXAMPLES",     _FCL_COMMON_EXAMPLES,     "FCL — common examples (all lanes)"),
    ("_FCL_IMPORT_EXAMPLES",     _FCL_IMPORT_EXAMPLES,     "FCL + Import — combination-specific notes/examples"),
    ("_FCL_EXPORT_EXAMPLES",     _FCL_EXPORT_EXAMPLES,     "FCL + Export — combination-specific notes/examples"),
    ("_FCL_CROSSTRADE_EXAMPLES", _FCL_CROSSTRADE_EXAMPLES, "FCL + Cross Trade — combination-specific notes/examples"),
    ("_LCL_COMMON_EXAMPLES",     _LCL_COMMON_EXAMPLES,     "LCL — common examples (all lanes)"),
    ("_LCL_IMPORT_EXAMPLES",     _LCL_IMPORT_EXAMPLES,     "LCL + Import — combination-specific notes/examples"),
    ("_LCL_EXPORT_EXAMPLES",     _LCL_EXPORT_EXAMPLES,     "LCL + Export — combination-specific notes/examples"),
    ("_LCL_CROSSTRADE_EXAMPLES", _LCL_CROSSTRADE_EXAMPLES, "LCL + Cross Trade — combination-specific notes/examples"),
]

LANE_DATA = {
    "import":      _LANE_IMPORT,
    "export":      _LANE_EXPORT,
    "cross trade": _LANE_CROSSTRADE,
}
AIR_COMBO  = {"import": _AIR_IMPORT_EXAMPLES,  "export": _AIR_EXPORT_EXAMPLES,  "cross trade": _AIR_CROSSTRADE_EXAMPLES}
FCL_COMBO  = {"import": _FCL_IMPORT_EXAMPLES,  "export": _FCL_EXPORT_EXAMPLES,  "cross trade": _FCL_CROSSTRADE_EXAMPLES}
LCL_COMBO  = {"import": _LCL_IMPORT_EXAMPLES,  "export": _LCL_EXPORT_EXAMPLES,  "cross trade": _LCL_CROSSTRADE_EXAMPLES}

LANES = ["import", "export", "cross trade"]

AIR_ORDER = [
    ("_AIR_ROLE",          "AIR — system role"),
    ("_INQUIRY_FILTER",    "Shared — buyer/vendor filter + document format"),
    ("[LANE]",             "Lane block for the selected lane"),
    ("_AIR_RATE_NOTATION", "AIR — compact rate notation"),
    ("_AIR_BUCKETS",       "AIR — bucket definitions"),
    ("_AIR_CANONICAL",     "AIR — canonical charge names"),
    ("_AIR_COMMON_EXAMPLES", "AIR — common examples (all lanes)"),
    ("[COMBO]",            "AIR + Lane combination-specific notes"),
    ("_VERIFY",            "Shared — pre-return checklist"),
    ("--- separator ---",  "visual rule"),
    ("_AIR_JSON_SCHEMA",   "AIR — JSON schema + output rules"),
    ('"Extract all..."',   "closing instruction"),
]

FCL_ORDER = [
    ("_FCL_ROLE",                "FCL — system role"),
    ("_INQUIRY_FILTER",          "Shared — buyer/vendor filter + document format"),
    ("[LANE]",                   "Lane block for the selected lane"),
    ("_FCL_CONTAINER_SELECTION", "FCL — container type selection rules"),
    ("_FCL_BUCKETS",             "FCL — bucket definitions"),
    ("_FCL_CANONICAL",           "FCL — canonical charge names"),
    ("_FCL_COMMON_EXAMPLES",     "FCL — common examples (all lanes)"),
    ("[COMBO]",                  "FCL + Lane combination-specific notes"),
    ("_VERIFY",                  "Shared — pre-return checklist"),
    ("--- separator ---",        "visual rule"),
    ("_FCL_JSON_SCHEMA",         "FCL — JSON schema + output rules"),
    ('"Extract all..."',         "closing instruction"),
]

LCL_ORDER = [
    ("_LCL_ROLE",            "LCL — system role"),
    ("_INQUIRY_FILTER",      "Shared — buyer/vendor filter + document format"),
    ("[LANE]",               "Lane block for the selected lane"),
    ("_LCL_BUCKETS",         "LCL — bucket definitions"),
    ("_LCL_CANONICAL",       "LCL — canonical charge names"),
    ("_LCL_COMMON_EXAMPLES", "LCL — common examples (all lanes)"),
    ("[COMBO]",              "LCL + Lane combination-specific notes"),
    ("_VERIFY",              "Shared — pre-return checklist"),
    ("--- separator ---",    "visual rule"),
    ("_LCL_JSON_SCHEMA",     "LCL — JSON schema + output rules"),
    ('"Extract all..."',     "closing instruction"),
]

MODES = [
    ("AIR", AIR_ORDER, AIR_COMBO, AIR_MODE_BLOCKS),
    ("FCL", FCL_ORDER, FCL_COMBO, FCL_MODE_BLOCKS),
    ("LCL", LCL_ORDER, LCL_COMBO, LCL_MODE_BLOCKS),
]


def build(mode, lane):
    lane_section = f"\n\n{LANE_DATA[lane]}" if lane else ""
    combo = {"AIR": AIR_COMBO, "FCL": FCL_COMBO, "LCL": LCL_COMBO}[mode].get(lane, "")
    combo_section = f"\n\n{combo}" if combo else ""
    if mode == "AIR":
        return (
            f"{_AIR_ROLE}\n\n{_INQUIRY_FILTER}{lane_section}\n\n"
            f"{_AIR_RATE_NOTATION}\n\n{_AIR_BUCKETS}\n\n{_AIR_CANONICAL}\n\n"
            f"{_AIR_COMMON_EXAMPLES}{combo_section}\n\n{_VERIFY}\n\n"
            f"{SEP}\n{_AIR_JSON_SCHEMA}\n\nExtract all charges from the document(s) provided above."
        )
    if mode == "FCL":
        return (
            f"{_FCL_ROLE}\n\n{_INQUIRY_FILTER}{lane_section}\n\n"
            f"{_FCL_CONTAINER_SELECTION}\n\n{_FCL_BUCKETS}\n\n{_FCL_CANONICAL}\n\n"
            f"{_FCL_COMMON_EXAMPLES}{combo_section}\n\n{_VERIFY}\n\n"
            f"{SEP}\n{_FCL_JSON_SCHEMA}\n\nExtract all charges from the document(s) provided above."
        )
    return (
        f"{_LCL_ROLE}\n\n{_INQUIRY_FILTER}{lane_section}\n\n"
        f"{_LCL_BUCKETS}\n\n{_LCL_CANONICAL}\n\n"
        f"{_LCL_COMMON_EXAMPLES}{combo_section}\n\n{_VERIFY}\n\n"
        f"{SEP}\n{_LCL_JSON_SCHEMA}\n\nExtract all charges from the document(s) provided above."
    )


out = []

out.append("# Gemini Extraction Prompts — Reference\n")
out.append("> Generated from `src/services/prompts.py` and `src/services/gemini_service.py`.")
out.append("> Re-run `gen_prompts_ref.py` after editing those files.\n")
out.append("---\n")

out.append("## Contents\n")
out.append("**Part 1 — Raw Prompt Blocks**\n")
out.append("- [Shared Blocks](#shared-blocks)")
out.append("- [Lane Blocks](#lane-blocks)")
out.append("- [AIR Mode Blocks](#air-mode-blocks)")
out.append("- [FCL Mode Blocks](#fcl-mode-blocks)")
out.append("- [LCL Mode Blocks](#lcl-mode-blocks)")
out.append("- [Combination Blocks](#combination-blocks)\n")
out.append("**Part 2 — Assembly Map**\n")
for mode, _, _, _ in MODES:
    out.append(f"- [{mode} Assembly](#{mode.lower()}-assembly)")
out.append("")
out.append("**Part 3 — Full Assembled Prompts**\n")
for mode, _, _, _ in MODES:
    for lane in LANES:
        slug = f"{mode.lower()}-{lane.replace(' ', '-')}"
        out.append(f"- [{mode} + {lane.title()}](#{slug})")
out.append("\n---\n")

# ── PART 1 ─────────────────────────────────────────────────────────────────
out.append("# Part 1 — Raw Prompt Blocks\n")

def emit_blocks(title, anchor, blocks):
    out.append(f"## {title} {{#{anchor}}}\n")
    for name, content, desc in blocks:
        out.append(f"### `{name}`")
        out.append(f"*{desc}*\n")
        out.append("```")
        out.append(content)
        out.append("```\n")

emit_blocks("Shared Blocks",       "shared-blocks",       SHARED_BLOCKS)
emit_blocks("Lane Blocks",         "lane-blocks",         LANE_BLOCKS)
emit_blocks("AIR Mode Blocks",     "air-mode-blocks",     AIR_MODE_BLOCKS)
emit_blocks("FCL Mode Blocks",     "fcl-mode-blocks",     FCL_MODE_BLOCKS)
emit_blocks("LCL Mode Blocks",     "lcl-mode-blocks",     LCL_MODE_BLOCKS)
emit_blocks("Combination Blocks",  "combination-blocks",  COMBO_BLOCKS)
out.append("---\n")

# ── PART 2 ─────────────────────────────────────────────────────────────────
out.append("# Part 2 — Assembly Map\n")
out.append("> `[LANE]` = the lane block for the selected lane.")
out.append("> `[COMBO]` = the mode+lane combination block. Both are omitted when lane is blank.\n")

for mode, order, combo_map, mode_blocks in MODES:
    out.append(f"## {mode} Assembly {{#{mode.lower()}-assembly}}\n")
    out.append("### Block stitch order\n")
    out.append("| # | Block | Purpose |")
    out.append("|---|---|---|")
    for i, (block, desc) in enumerate(order, 1):
        out.append(f"| {i} | `{block}` | {desc} |")
    out.append("")

    out.append("### Combination blocks per lane\n")
    out.append("| Lane | `[LANE]` block | `[COMBO]` block |")
    out.append("|---|---|---|")
    lane_name_map = {"import": "_LANE_IMPORT", "export": "_LANE_EXPORT", "cross trade": "_LANE_CROSSTRADE"}
    combo_name_map = {
        "AIR": {"import": "_AIR_IMPORT_EXAMPLES", "export": "_AIR_EXPORT_EXAMPLES", "cross trade": "_AIR_CROSSTRADE_EXAMPLES"},
        "FCL": {"import": "_FCL_IMPORT_EXAMPLES", "export": "_FCL_EXPORT_EXAMPLES", "cross trade": "_FCL_CROSSTRADE_EXAMPLES"},
        "LCL": {"import": "_LCL_IMPORT_EXAMPLES", "export": "_LCL_EXPORT_EXAMPLES", "cross trade": "_LCL_CROSSTRADE_EXAMPLES"},
    }
    for lane in LANES:
        out.append(f"| **{lane.title()}** | `{lane_name_map[lane]}` | `{combo_name_map[mode][lane]}` |")
    out.append("")

    other = []
    for om, _, _, ob in MODES:
        if om != mode:
            for n, _, _ in ob:
                other.append(f"`{n}` ({om})")
    out.append(f"### Blocks NOT used in {mode}\n")
    out.append(", ".join(other) + "\n")

out.append("---\n")

# ── PART 3 ─────────────────────────────────────────────────────────────────
out.append("# Part 3 — Full Assembled Prompts\n")

for mode, order, _, _ in MODES:
    stitch = " → ".join(b for b, _ in order)
    for lane in LANES:
        slug = f"{mode.lower()}-{lane.replace(' ', '-')}"
        out.append("---\n")
        out.append(f"## {mode} + {lane.title()} {{#{slug}}}\n")
        out.append(f"**Stitch:** `{stitch}`\n")
        out.append("```")
        out.append(build(mode, lane))
        out.append("```\n")

content = "\n".join(out)
with open("PROMPTS_REFERENCE.md", "w", encoding="utf-8") as f:
    f.write(content)

print(f"Written: PROMPTS_REFERENCE.md ({len(content):,} chars, {content.count(chr(10))} lines)")
