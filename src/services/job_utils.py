import re
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Job-number regex: E followed by 6 digits (case-insensitive)
JOB_RE = re.compile(r"\bE\d{6}\b", re.I)


def extract_jobs_from_text(text: str) -> List[str]:
    """Return all job-number matches from free text, uppercased."""
    if not text:
        return []
    return [m.group(0).upper() for m in JOB_RE.finditer(text)]


def extract_job_from_subject(text: str) -> Optional[str]:
    """Search Subject: lines first and return first job found, or None."""
    if not text:
        return None
    # Find Subject lines (multiline, case-insensitive)
    subs = re.findall(r"(?mi)^Subject:\s*(.+)$", text)
    for s in subs:
        m = JOB_RE.search(s)
        if m:
            return m.group(0).upper()
    return None


def find_job_in_file(path: str, parse_file_func=None) -> Optional[str]:
    """Parse the file (using provided parse_file_func or import) and return
    the first job number found in the Subject lines, falling back to any match
    found anywhere in the text. Returns uppercased job (e.g. 'E260190') or None.
    """
    try:
        if parse_file_func is None:
            # Lazy import to avoid heavy deps at module import time
            from src.services.email_parser import parse_file as _pf
            parse_file_func = _pf

        text = parse_file_func(path)
        if not text:
            return None

        job = extract_job_from_subject(text)
        if job:
            return job

        jobs = extract_jobs_from_text(text)
        return jobs[0] if jobs else None
    except Exception as exc:
        logger.debug("find_job_in_file(%s) failed: %s", path, exc)
        return None
