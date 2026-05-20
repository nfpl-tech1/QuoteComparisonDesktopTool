import logging
import os
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def parse_pdf(file_path: str) -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
            for table in page.extract_tables():
                if not table:
                    continue
                for row in table:
                    cells = [str(c).strip() if c else "" for c in row]
                    parts.append(" | ".join(cells))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTML → text (preserves table/cell structure for Gemini)
# ---------------------------------------------------------------------------
def _html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        # Keep cell boundaries readable
        for td in soup.find_all(["td", "th"]):
            td.insert_after(" | ")
        for tr in soup.find_all("tr"):
            tr.insert_after("\n")
        return soup.get_text(" ", strip=True)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Body extractor (works on both Message and embedded MSGFile objects)
# ---------------------------------------------------------------------------
def _msg_body(msg_obj) -> str:
    body = getattr(msg_obj, "body", None) or ""

    if not body:
        html = getattr(msg_obj, "htmlBody", None)
        if html:
            if isinstance(html, bytes):
                html = html.decode("utf-8", errors="replace")
            body = _html_to_text(html)

    subject = getattr(msg_obj, "subject", None) or ""
    sender  = getattr(msg_obj, "sender",  None) or ""
    header  = "\n".join(filter(None, [
        f"Subject: {subject}" if subject else "",
        f"From: {sender}"    if sender  else "",
    ]))
    return f"{header}\n\n{body}".strip() if header else body.strip()


# ---------------------------------------------------------------------------
# Attachment walker — returns list of text blobs
# ---------------------------------------------------------------------------
def _walk_attachments(msg_obj) -> list[str]:
    parts: list[str] = []
    attachments = getattr(msg_obj, "attachments", None) or []

    for att in attachments:
        data = getattr(att, "data", None)
        if data is None:
            continue

        # ── Embedded MSGFile (extract-msg MSGAttachment) ──────────────
        # att.data is an MSGFile instance, not bytes
        if hasattr(data, "body") or hasattr(data, "attachments"):
            try:
                nested_body  = _msg_body(data)
                nested_parts = _walk_attachments(data)
                all_p = [p for p in [nested_body] + nested_parts if p.strip()]
                if all_p:
                    parts.append("[Embedded Email]\n" + "\n\n".join(all_p))
            except Exception as exc:
                logger.debug("embedded MSG parse failed: %s", exc)
            continue

        if not isinstance(data, (bytes, bytearray)) or not data:
            continue

        # ── Determine filename ────────────────────────────────────────
        fname = (
            getattr(att, "longFilename",  None)
            or getattr(att, "shortFilename", None)
            or getattr(att, "name",          None)
            or ""
        ).strip()
        ext = Path(fname).suffix.lower() if fname else ""

        # ── PDF attachment ─────────────────────────────────────────────
        if ext == ".pdf" or (not ext and _looks_like_pdf(data)):
            suffix = ".pdf"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                pdf_text = parse_pdf(tmp_path)
                if pdf_text.strip():
                    label = f"[PDF: {fname}]" if fname else "[PDF Attachment]"
                    parts.append(f"{label}\n{pdf_text}")
            except Exception as exc:
                logger.debug("PDF parse failed (%s): %s", fname, exc)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        # ── Nested .msg attachment ─────────────────────────────────────
        elif ext == ".msg":
            with tempfile.NamedTemporaryFile(suffix=".msg", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                import extract_msg as _em
                nested     = _em.Message(tmp_path)
                nested_body  = _msg_body(nested)
                nested_parts = _walk_attachments(nested)
                all_p = [p for p in [nested_body] + nested_parts if p.strip()]
                if all_p:
                    label = f"[Attached MSG: {fname}]" if fname else "[Attached MSG]"
                    parts.append(label + "\n" + "\n\n".join(all_p))
            except Exception as exc:
                logger.debug("nested MSG parse failed (%s): %s", fname, exc)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    return parts


def _looks_like_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_msg(file_path: str) -> str:
    import extract_msg
    msg   = extract_msg.Message(file_path)
    body  = _msg_body(msg)
    atts  = _walk_attachments(msg)
    parts = [p for p in [body] + atts if p.strip()]
    result = "\n\n".join(parts)
    logger.debug("parse_msg(%s): body=%d chars, attachments=%d, total=%d chars",
                 Path(file_path).name, len(body), len(atts), len(result))
    return result


def parse_file(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(file_path)
    if suffix == ".msg":
        return parse_msg(file_path)
    raise ValueError(f"Unsupported file type: {suffix}")
