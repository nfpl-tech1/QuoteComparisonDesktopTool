"""
Inquiry session persistence.

One session file per (inquiry_number, mode) pair.
Sessions are saved into the user's app-data directory, with legacy
repo-local Data/Sessions/ files still readable for backward compatibility.

Session identity for skip-re-extraction: source_file path + size + mtime.
"""
import json
import os
from datetime import datetime
from pathlib import Path

from src.services.app_paths import legacy_sessions_dir, sessions_dir

SESSIONS_DIR = sessions_dir()


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
def session_path(inquiry: str, mode: str) -> Path:
    return SESSIONS_DIR / f"{inquiry.upper()}-{mode.upper()}.json"


def session_exists(inquiry: str, mode: str) -> bool:
    return _find_session_path(inquiry, mode) is not None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
def list_sessions() -> list[dict]:
    """Return metadata for all saved sessions, newest-saved first."""
    results = []
    seen_paths: set[str] = set()
    for base_dir in _session_search_dirs():
        if not base_dir.exists():
            continue
        for f in base_dir.glob("*-*.json"):
            try:
                resolved = str(f.resolve())
            except Exception:
                resolved = str(f)
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                results.append({
                    "inquiry": data.get("inquiry_number", ""),
                    "mode": data.get("mode", "").upper(),
                    "saved_at": data.get("saved_at", ""),
                    "vendor_count": len(data.get("vendors", [])),
                    "path": str(f),
                })
            except Exception:
                pass
    results.sort(key=lambda x: x["saved_at"], reverse=True)
    return results


def saved_inquiries_for_mode(mode: str) -> list[str]:
    """Return inquiry numbers that have a saved session for the given mode."""
    return [
        s["inquiry"] for s in list_sessions()
        if s["mode"].upper() == mode.upper() and s["inquiry"]
    ]


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
def save_session(app) -> Path | None:
    """Serialize current app state to {AppData}/Sessions/{INQUIRY}-{MODE}.json."""
    inquiry = getattr(app, "inquiry_number", "").strip().upper()
    mode = getattr(app, "selected_quote_mode", "").strip().upper()
    if not inquiry or not mode:
        return None

    sessions_dir().mkdir(parents=True, exist_ok=True)

    vendors_data = []
    for vd in app.vendors.values():
        d = vd.to_dict()
        try:
            stat = os.stat(vd.source_file)
            d["file_size"] = stat.st_size
            d["file_mtime"] = stat.st_mtime
        except OSError:
            d["file_size"] = 0
            d["file_mtime"] = 0.0
        vendors_data.append(d)

    session = {
        "inquiry_number": inquiry,
        "mode": mode,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "chargeable_weight": getattr(app, "chargeable_weight", 0.0),
        "vendors": vendors_data,
    }

    path = session_path(inquiry, mode)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_session(inquiry: str, mode: str) -> dict | None:
    """Return raw session dict, or None if file not found / unreadable."""
    path = _find_session_path(inquiry, mode)
    if path is None:
        return None
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# File identity helpers
# ---------------------------------------------------------------------------
def file_is_known(source_file: str, session: dict) -> bool:
    """Return True if this file already exists unchanged in the session."""
    try:
        stat = os.stat(source_file)
        size = stat.st_size
        mtime = stat.st_mtime
    except OSError:
        return False
    for vd in session.get("vendors", []):
        if (vd.get("source_file") == source_file
                and vd.get("file_size") == size
                and abs(vd.get("file_mtime", 0) - mtime) < 1.0):
            return True
    return False


def vendors_for_file(source_file: str, session: dict) -> list[dict]:
    """Return all vendor dicts from the session that came from this source file."""
    return [v for v in session.get("vendors", []) if v.get("source_file") == source_file]


def _session_search_dirs() -> list[Path]:
    dirs = [sessions_dir()]
    legacy = legacy_sessions_dir()
    try:
        legacy_resolved = legacy.resolve()
        current_resolved = sessions_dir().resolve()
    except Exception:
        legacy_resolved = legacy
        current_resolved = sessions_dir()
    if legacy.exists() and legacy_resolved != current_resolved:
        dirs.append(legacy)
    return dirs


def _find_session_path(inquiry: str, mode: str) -> Path | None:
    filename = f"{inquiry.upper()}-{mode.upper()}.json"
    for base_dir in _session_search_dirs():
        candidate = base_dir / filename
        if candidate.exists():
            return candidate
    return None
