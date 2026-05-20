import json
import os

from src.services.app_paths import settings_file


DEFAULT_SETTINGS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "free_currency_api_key": "",
}


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
        except Exception:
            pass

    if not data["gemini_api_key"]:
        data["gemini_api_key"] = os.getenv("GEMINI_API_KEY", "").strip()
    if not data["free_currency_api_key"]:
        data["free_currency_api_key"] = os.getenv("FREE_CURRENCY_API_KEY", "").strip()
    if not data["gemini_model"]:
        data["gemini_model"] = DEFAULT_SETTINGS["gemini_model"]
    return data


def save_settings(settings: dict) -> None:
    payload = {key: str(settings.get(key, DEFAULT_SETTINGS[key]) or "") for key in DEFAULT_SETTINGS}
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def masked(value: str) -> str:
    value = str(value or "").strip()
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * (len(value) - 8)}{value[-4:]}"
