import os
import sys
from pathlib import Path


APP_VENDOR = "Nagarkot"
APP_NAME = "VendorQuoteComparisonTool"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return project_root()


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def app_data_dir() -> Path:
    base = os.getenv("APPDATA")
    if base:
        path = Path(base) / APP_VENDOR / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def rates_cache_file() -> Path:
    return app_data_dir() / "rates_cache.json"


def sessions_dir() -> Path:
    path = app_data_dir() / "Sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def legacy_sessions_dir() -> Path:
    return project_root() / "Data" / "Sessions"
