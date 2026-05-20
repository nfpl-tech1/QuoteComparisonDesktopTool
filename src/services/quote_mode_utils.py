import re
from typing import Optional


_AIR_PATTERNS = (
    r"\bair freight\b",
    r"\bawb\b",
    r"\bairline\b",
    r"\bflight\b",
    r"\bkg\b",
    r"\bfsc\b",
)

_FCL_PATTERNS = (
    r"\bocean freight\b",
    r"\b20gp\b",
    r"\b40gp\b",
    r"\b40hq\b",
    r"\b40hc\b",
    r"\b20ft\b",
    r"\b40ft\b",
    r"\bfcl\b",
    r"\bper container\b",
    r"\bfree time\b",
    r"\bshipping line\b",
)

_LCL_PATTERNS = (
    r"\blcl\b",
    r"\bgroupage\b",
    r"\bw/m\b",
    r"\bper cbm\b",
    r"\b/cbm\b",
    r"\bcbm\b",
    r"\bper ton\b",
)


def guess_quote_mode_from_text(text: str) -> tuple[str, int]:
    text = (text or "").lower()
    scores = {
        "air": _score_patterns(text, _AIR_PATTERNS),
        "fcl": _score_patterns(text, _FCL_PATTERNS),
        "lcl": _score_patterns(text, _LCL_PATTERNS),
    }
    mode, score = max(scores.items(), key=lambda kv: kv[1])
    if score <= 0:
        return "", 0

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
        return "", 0
    return mode, score


def guess_quote_mode_in_file(path: str, parse_file_func=None) -> tuple[str, int]:
    if parse_file_func is None:
        from src.services.email_parser import parse_file as _pf
        parse_file_func = _pf
    try:
        text = parse_file_func(path)
    except Exception:
        return "", 0
    return guess_quote_mode_from_text(text[:8000])


def is_strong_mode_mismatch(selected_mode: str, guessed_mode: str, score: int) -> bool:
    selected_mode = (selected_mode or "").strip().lower()
    guessed_mode = (guessed_mode or "").strip().lower()
    if not selected_mode or not guessed_mode or selected_mode == guessed_mode:
        return False
    return score >= 2


def _score_patterns(text: str, patterns: tuple[str, ...]) -> int:
    score = 0
    for pattern in patterns:
        if re.search(pattern, text):
            score += 1
    return score
