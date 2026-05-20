"""
Scan Data/TestInputData and rank files by lightweight AIR/FCL/LCL heuristics.

Useful for quickly identifying candidate sample files for regression testing.

Run with:
    .\\venv\\Scripts\\python tools/find_mode_candidates.py
"""

import os
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services.email_parser import parse_file
from src.services.quote_mode_utils import guess_quote_mode_from_text

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def main():
    root = ROOT / "Data" / "TestInputData"
    ranked: dict[str, list[tuple[int, str]]] = {"air": [], "fcl": [], "lcl": []}

    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.lower().endswith((".msg", ".pdf")):
                continue
            path = Path(dirpath) / filename
            try:
                text = parse_file(str(path))
            except Exception:
                continue
            mode, score = guess_quote_mode_from_text(text[:8000])
            if mode:
                ranked[mode].append((score, str(path.relative_to(ROOT))))

    for mode in ("air", "fcl", "lcl"):
        print("=" * 100)
        print(mode.upper())
        entries = sorted(ranked[mode], key=lambda item: (-item[0], item[1]))
        if not entries:
            print("  No candidates found.")
            continue
        for score, rel_path in entries[:25]:
            safe_path = rel_path.encode("ascii", "replace").decode()
            print(f"  score={score:<2}  {safe_path}")


if __name__ == "__main__":
    main()
