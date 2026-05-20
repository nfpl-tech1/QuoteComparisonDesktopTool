import json
import re

from google import genai
from google.genai import types

from src.services.prompts import (
    _INQUIRY_FILTER, _VERIFY,
    _AIR_ROLE, _AIR_BUCKETS, _AIR_CANONICAL, _AIR_EXAMPLES, _AIR_JSON_SCHEMA,
    _FCL_ROLE, _FCL_BUCKETS, _FCL_CANONICAL, _FCL_CONTAINER_SELECTION,
    _FCL_EXAMPLES, _FCL_JSON_SCHEMA,
    _LCL_ROLE, _LCL_BUCKETS, _LCL_CANONICAL, _LCL_EXAMPLES, _LCL_JSON_SCHEMA,
    _DETECT_PROMPT_TPL,
)


class GeminiService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self._client = genai.Client(api_key=api_key)
        self.model_name = str(model_name or "gemini-2.5-flash").strip()
        self._extract_config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            thinking_config=types.ThinkingConfig(thinking_budget=8192),
        )
        self._detect_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=512),
        )

    def extract_charges(self, document_text: str, selected_mode: str = "") -> list[dict]:
        """Return a list of vendor-data dicts — one per quote_type / shipping_line."""
        qt = str(selected_mode or "").lower().strip()
        if qt not in ("air", "fcl", "lcl"):
            qt = self._detect_type(document_text)
        if qt == "fcl":
            return self._extract_fcl(document_text)
        elif qt == "lcl":
            return self._extract_lcl(document_text)
        elif qt == "mixed":
            air_res = self._extract_air(document_text)
            sea_res = self._extract_sea_for_mixed(document_text)
            return air_res + sea_res
        else:  # default: air
            return self._extract_air(document_text)

    # ------------------------------------------------------------------
    def _detect_type(self, text: str) -> str:
        prompt = _DETECT_PROMPT_TPL.format(
            inquiry_filter=_INQUIRY_FILTER,
            text=text[:4000],
        )
        try:
            data = self._call_for_json(prompt, self._detect_config)
            qt = str(data.get("quote_type", "air")).lower().strip()
            return qt if qt in ("air", "fcl", "lcl", "mixed") else "air"
        except Exception:
            return "air"

    def _extract_air(self, text: str) -> list[dict]:
        data = self._call_for_json(self._build_air_prompt(text), self._extract_config)
        vendor_name = data.get("vendor_name") or "Unknown Vendor"
        airline_entries = data.get("airlines", [])
        if not airline_entries:
            # fallback: legacy flat response or malformed JSON
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

    def _extract_fcl(self, text: str) -> list[dict]:
        data = self._call_for_json(self._build_fcl_prompt(text), self._extract_config)
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
                "vendor_name":           vendor_name,
                "quote_type":            "fcl",
                "shipping_line":         "",
                "container_type":        "",
                "etd":                   "",
                "transit_days":          "",
                "free_days_origin":      0,
                "free_days_destination": 0,
                "charges":               [],
            })
        return results

    def _extract_lcl(self, text: str) -> list[dict]:
        data = self._call_for_json(self._build_lcl_prompt(text), self._extract_config)
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

    def _extract_sea_for_mixed(self, text: str) -> list[dict]:
        """For mixed docs: try FCL first, fall back to LCL."""
        text_lower = text.lower()
        if any(k in text_lower for k in ("20ft", "40ft", "20'", "40'", "fcl", "full container")):
            return self._extract_fcl(text)
        return self._extract_lcl(text)

    # ------------------------------------------------------------------
    def _call(self, prompt: str, config) -> str:
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        return response.text

    def _call_for_json(self, prompt: str, config) -> dict:
        raw = self._call(prompt, config)
        try:
            return self._parse_json(raw)
        except json.JSONDecodeError:
            retry_prompt = (
                prompt
                + "\n\nIMPORTANT RETRY INSTRUCTION:\n"
                + "Your previous response was not valid JSON. "
                + "Return ONLY one valid JSON object matching the requested schema. "
                + "Do not add markdown fences, commentary, or any text before/after the JSON."
            )
            retry_raw = self._call(retry_prompt, config)
            return self._parse_json(retry_raw)

    def _build_air_prompt(self, text: str) -> str:
        return f"""{_AIR_ROLE}

{_INQUIRY_FILTER}

{_AIR_BUCKETS}

{_AIR_CANONICAL}

{_AIR_EXAMPLES}

{_VERIFY}

─────────────────────────────────────────────────────────────────────────────
{_AIR_JSON_SCHEMA}

DOCUMENT:
{text[:12000]}"""

    def _build_fcl_prompt(self, text: str) -> str:
        return f"""{_FCL_ROLE}

{_INQUIRY_FILTER}

{_FCL_CONTAINER_SELECTION}

{_FCL_BUCKETS}

{_FCL_CANONICAL}

{_FCL_EXAMPLES}

{_VERIFY}

─────────────────────────────────────────────────────────────────────────────
{_FCL_JSON_SCHEMA}

DOCUMENT:
{text[:12000]}"""

    def _build_lcl_prompt(self, text: str) -> str:
        return f"""{_LCL_ROLE}

{_INQUIRY_FILTER}

{_LCL_BUCKETS}

{_LCL_CANONICAL}

{_LCL_EXAMPLES}

{_VERIFY}

─────────────────────────────────────────────────────────────────────────────
{_LCL_JSON_SCHEMA}

DOCUMENT:
{text[:12000]}"""

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
