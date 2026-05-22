import json
import os

from src.services.app_paths import settings_file

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
SUPPORTED_GEMINI_MODELS = {
    DEFAULT_GEMINI_MODEL,
    "gemini-2.5-flash",
}


DEFAULT_SETTINGS = {
    "gemini_api_key": "",
    "gemini_model": DEFAULT_GEMINI_MODEL,
    "cloud_service_url": "",
    "cloud_api_key": "",
    "user_display_name": "",
}


def normalize_gemini_model(value: str) -> str:
    model = str(value or "").strip()
    return model if model in SUPPORTED_GEMINI_MODELS else DEFAULT_GEMINI_MODEL


def load_settings() -> dict:
    data = dict(DEFAULT_SETTINGS)
    path = settings_file()
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for key in DEFAULT_SETTINGS:
                    value = loaded.get(key)
                    if value is not None:
                        data[key] = str(value)
                # Migrate old free_currency_api_key installs gracefully
                if loaded.get("free_currency_api_key") and not data["cloud_api_key"]:
                    data["cloud_api_key"] = str(loaded["free_currency_api_key"])
        except Exception:
            pass

    if not data["gemini_api_key"]:
        data["gemini_api_key"] = os.getenv("GEMINI_API_KEY", "").strip()
    if not data["cloud_service_url"]:
        data["cloud_service_url"] = os.getenv("CLOUD_SERVICE_URL", "").strip()
    if not data["cloud_api_key"]:
        data["cloud_api_key"] = os.getenv("CLOUD_API_KEY", "").strip()
    data["gemini_model"] = normalize_gemini_model(data["gemini_model"])
    return data


def save_settings(settings: dict) -> None:
    payload = {key: str(settings.get(key, DEFAULT_SETTINGS[key]) or "") for key in DEFAULT_SETTINGS}
    payload["gemini_model"] = normalize_gemini_model(payload["gemini_model"])
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def masked(value: str) -> str:
    value = str(value or "").strip()
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * (len(value) - 8)}{value[-4:]}"
