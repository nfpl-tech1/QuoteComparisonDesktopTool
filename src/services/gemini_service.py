import json
import os
import re
import tempfile
import time

from google import genai
from google.genai import types

from src.services.prompts import (
    _INQUIRY_FILTER, _VERIFY, _LANE_CONTEXT_TPL, _LANE_DETAILS,
    _AIR_ROLE, _AIR_BUCKETS, _AIR_CANONICAL, _AIR_RATE_NOTATION, _AIR_EXAMPLES, _AIR_JSON_SCHEMA,
    _FCL_ROLE, _FCL_BUCKETS, _FCL_CANONICAL, _FCL_CONTAINER_SELECTION,
    _FCL_EXAMPLES, _FCL_JSON_SCHEMA,
    _LCL_ROLE, _LCL_BUCKETS, _LCL_CANONICAL, _LCL_EXAMPLES, _LCL_JSON_SCHEMA,
)
from src.services.email_parser import DocumentParts, decompose_file

_FALLBACK_MODEL = "gemini-2.5-flash"


class GeminiService:
    def __init__(self, api_key: str, model_name: str = "gemini-3.1-flash-lite"):
        self._client = genai.Client(api_key=api_key)
        self.model_name = str(model_name or "gemini-3.1-flash-lite").strip()
        self._extract_config = types.GenerateContentConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_charges(self, file_path: str, selected_mode: str = "", selected_lane: str = "") -> list[dict]:
        """Decompose file, upload PDFs to File API, extract charges via Gemini."""
        doc = decompose_file(file_path)
        qt = str(selected_mode).lower().strip()
        lane = str(selected_lane).lower().strip()
        uploaded = self._upload_pdfs(doc.pdf_bytes)
        try:
            if qt == "fcl":
                return self._extract_fcl(doc, uploaded, lane)
            elif qt == "lcl":
                return self._extract_lcl(doc, uploaded, lane)
            elif qt == "mixed":
                return self._extract_air(doc, uploaded, lane) + self._extract_sea_for_mixed(doc, uploaded, lane)
            else:
                return self._extract_air(doc, uploaded, lane)
        finally:
            self._delete_uploaded(uploaded)

    # ------------------------------------------------------------------
    # File API helpers
    # ------------------------------------------------------------------
    def _upload_pdfs(self, pdf_bytes: list[tuple[str, bytes]]) -> list:
        """Upload each PDF to the File API and wait for ACTIVE state."""
        uploaded = []
        for label, data in pdf_bytes:
            ref = self._upload_single_pdf(label, data)
            if ref:
                uploaded.append(ref)
        return uploaded

    def _upload_single_pdf(self, label: str, data: bytes):
        suffix = ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            ref = self._client.files.upload(
                file=tmp_path,
                config=types.UploadFileConfig(
                    mime_type="application/pdf",
                    display_name=label[:40],
                ),
            )
            for _ in range(10):
                state = str(getattr(ref, "state", "")).upper()
                if "ACTIVE" in state:
                    return ref
                if "FAIL" in state:
                    return None
                time.sleep(1)
                ref = self._client.files.get(name=ref.name)
            return ref
        except Exception as exc:
            import logging
            logging.getLogger(__name__).debug("PDF upload failed (%s): %s", label, exc)
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _delete_uploaded(self, uploaded: list) -> None:
        for ref in uploaded:
            try:
                self._client.files.delete(name=ref.name)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Contents builder
    # ------------------------------------------------------------------
    def _build_contents(self, instruction: str, doc: DocumentParts, uploaded: list) -> list:
        """Combine uploaded file refs + text parts + instruction into a contents list."""
        contents = []
        for ref in uploaded:
            contents.append(types.Part.from_uri(file_uri=ref.uri, mime_type=ref.mime_type))
        text_block = "\n\n---\n\n".join(doc.text_parts)
        if text_block:
            contents.append(f"{instruction}\n\nDOCUMENT TEXT:\n{text_block}")
        else:
            contents.append(instruction)
        return contents

    # ------------------------------------------------------------------
    # Extractors
    # ------------------------------------------------------------------
    def _extract_air(self, doc: DocumentParts, uploaded: list, lane: str = "") -> list[dict]:
        instruction = self._build_air_instruction(lane)

        contents = self._build_contents(instruction, doc, uploaded)
        data = self._call_for_json(contents, self._extract_config)

        vendor_name = data.get("vendor_name") or "Unknown Vendor"
        airline_entries = data.get("airlines", [])
        if not airline_entries:
            airline_entries = [{
                "airline_name": "",
                "transit_days": data.get("transit_days", ""),
                "charges":      data.get("charges", []),
            }]
        results = []
        for al in airline_entries:
            results.append({
                "vendor_name":           vendor_name,
                "quote_type":            "air",
                "airline":               str(al.get("airline_name") or "").strip(),
                "shipping_line":         "",
                "container_type":        "",
                "etd":                   str(al.get("etd") or ""),
                "transit_days":          str(al.get("transit_days") or ""),
                "free_days_origin":      0,
                "free_days_destination": 0,
                "charges":               self._coerce_charges(al.get("charges", [])),
            })
        return results

    def _extract_fcl(self, doc: DocumentParts, uploaded: list, lane: str = "") -> list[dict]:
        contents = self._build_contents(self._build_fcl_instruction(lane), doc, uploaded)
        data = self._call_for_json(contents, self._extract_config)
        vendor_name = data.get("vendor_name") or "Unknown Vendor"
        results = []
        for sl in data.get("shipping_lines", []):
            try:
                free_orig = int(sl.get("free_days_origin") or 0)
            except (ValueError, TypeError):
                free_orig = 0
            try:
                free_dest = int(sl.get("free_days_destination") or 0)
            except (ValueError, TypeError):
                free_dest = 0
            results.append({
                "vendor_name":           vendor_name,
                "quote_type":            "fcl",
                "shipping_line":         sl.get("shipping_line") or "",
                "container_type":        sl.get("container_type") or "",
                "etd":                   str(sl.get("etd") or ""),
                "transit_days":          str(sl.get("transit_days") or ""),
                "free_days_origin":      free_orig,
                "free_days_destination": free_dest,
                "charges":               self._coerce_charges(sl.get("charges", [])),
            })
        if not results:
            results.append({
                "vendor_name": vendor_name, "quote_type": "fcl",
                "shipping_line": "", "container_type": "", "etd": "",
                "transit_days": "", "free_days_origin": 0,
                "free_days_destination": 0, "charges": [],
            })
        return results

    def _extract_lcl(self, doc: DocumentParts, uploaded: list, lane: str = "") -> list[dict]:
        contents = self._build_contents(self._build_lcl_instruction(lane), doc, uploaded)
        data = self._call_for_json(contents, self._extract_config)
        try:
            free_orig = int(data.get("free_days_origin") or 0)
        except (ValueError, TypeError):
            free_orig = 0
        try:
            free_dest = int(data.get("free_days_destination") or 0)
        except (ValueError, TypeError):
            free_dest = 0
        return [{
            "vendor_name":           data.get("vendor_name") or "Unknown Vendor",
            "quote_type":            "lcl",
            "shipping_line":         "",
            "container_type":        "",
            "etd":                   str(data.get("etd") or ""),
            "transit_days":          str(data.get("transit_days") or ""),
            "free_days_origin":      free_orig,
            "free_days_destination": free_dest,
            "charges":               self._coerce_charges(data.get("charges", [])),
        }]

    def _extract_sea_for_mixed(self, doc: DocumentParts, uploaded: list, lane: str = "") -> list[dict]:
        combined = "\n".join(doc.text_parts).lower()
        if any(k in combined for k in ("20ft", "40ft", "20'", "40'", "fcl", "full container")):
            return self._extract_fcl(doc, uploaded, lane)
        return self._extract_lcl(doc, uploaded, lane)

    # ------------------------------------------------------------------
    # Prompt instructions (no document text embedded — that comes via _build_contents)
    # ------------------------------------------------------------------
    def _build_lane_context(self, lane: str) -> str:
        lane = lane.lower().strip()
        detail = _LANE_DETAILS.get(lane, "")
        if not lane or not detail:
            return ""
        return _LANE_CONTEXT_TPL.format(lane=lane.title(), lane_detail=detail)

    def _build_air_instruction(self, lane: str = "") -> str:
        lane_section = f"\n\n{self._build_lane_context(lane)}" if lane else ""
        return f"""{_AIR_ROLE}

{_INQUIRY_FILTER}{lane_section}

{_AIR_RATE_NOTATION}

{_AIR_BUCKETS}

{_AIR_CANONICAL}

{_AIR_EXAMPLES}

{_VERIFY}

─────────────────────────────────────────────────────────────────────────────
{_AIR_JSON_SCHEMA}

Extract all charges from the document(s) provided above."""

    def _build_fcl_instruction(self, lane: str = "") -> str:
        lane_section = f"\n\n{self._build_lane_context(lane)}" if lane else ""
        return f"""{_FCL_ROLE}

{_INQUIRY_FILTER}{lane_section}

{_FCL_CONTAINER_SELECTION}

{_FCL_BUCKETS}

{_FCL_CANONICAL}

{_FCL_EXAMPLES}

{_VERIFY}

─────────────────────────────────────────────────────────────────────────────
{_FCL_JSON_SCHEMA}

Extract all charges from the document(s) provided above."""

    def _build_lcl_instruction(self, lane: str = "") -> str:
        lane_section = f"\n\n{self._build_lane_context(lane)}" if lane else ""
        return f"""{_LCL_ROLE}

{_INQUIRY_FILTER}{lane_section}

{_LCL_BUCKETS}

{_LCL_CANONICAL}

{_LCL_EXAMPLES}

{_VERIFY}

─────────────────────────────────────────────────────────────────────────────
{_LCL_JSON_SCHEMA}

Extract all charges from the document(s) provided above."""

    # ------------------------------------------------------------------
    # API call helpers
    # ------------------------------------------------------------------
    def _call(self, contents, config) -> str:
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )
        return response.text

    def _call_for_json(self, contents, config) -> dict:
        raw = self._call(contents, config)
        try:
            return self._parse_json(raw)
        except json.JSONDecodeError:
            retry_msg = (
                "IMPORTANT RETRY INSTRUCTION: "
                "Your previous response was not valid JSON. "
                "Return ONLY one valid JSON object matching the requested schema. "
                "Do not add markdown fences, commentary, or any text before/after the JSON."
            )
            if isinstance(contents, list):
                retry_contents = contents + [retry_msg]
            else:
                retry_contents = contents + "\n\n" + retry_msg
            retry_raw = self._call(retry_contents, config)
            try:
                return self._parse_json(retry_raw)
            except json.JSONDecodeError:
                # Primary model failed twice — escalate to fallback model
                fallback_response = self._client.models.generate_content(
                    model=_FALLBACK_MODEL,
                    contents=retry_contents,
                    config=config,
                )
                return self._parse_json(fallback_response.text)

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------
    def _parse_json(self, text: str) -> dict:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        candidates = [cleaned]
        extracted = self._extract_json_payload(cleaned)
        if extracted and extracted not in candidates:
            candidates.append(extracted)

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        raise json.JSONDecodeError("Could not parse JSON payload", cleaned, 0)

    def _extract_json_payload(self, text: str) -> str:
        start = None
        opener = ""
        for idx, ch in enumerate(text):
            if ch in "{[":
                start = idx
                opener = ch
                break
        if start is None:
            return ""

        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == opener:
                depth += 1
                continue
            if ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start:idx + 1]

        last = text.rfind(closer)
        if last > start:
            return text[start:last + 1]
        return ""

    def _coerce_charges(self, charges: list) -> list[dict]:
        result = []
        for charge in charges:
            try:
                charge["rate"] = float(charge.get("rate") or 0)
            except (ValueError, TypeError):
                charge["rate"] = 0.0
            charge.setdefault("category", "")
            charge.setdefault("name_of_charge", "")
            charge.setdefault("currency", "USD")
            charge.setdefault("unit_of_measurement", "")
            charge.setdefault("remarks", "")
            charge["if_applicable"] = bool(charge.get("if_applicable", False))
            result.append(charge)
        return result
