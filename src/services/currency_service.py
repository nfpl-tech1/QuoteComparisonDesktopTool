import json
import requests
from datetime import date, datetime

from src.services.app_paths import rates_cache_file

FALLBACK_RATES = {
    "USD": 1.0,  "INR": 84.5,  "EUR": 0.92,  "GBP": 0.79,
    "AED": 3.67, "SGD": 1.35,  "CNY": 7.24,  "JPY": 149.5,
    "AUD": 1.53, "CAD": 1.36,  "THB": 35.2,  "MYR": 4.7,
    "HKD": 7.82, "CHF": 0.89,  "KRW": 1330.0,
}

_CACHE_FILE = rates_cache_file()


class CurrencyService:
    def __init__(self, cloud_url: str = "", cloud_api_key: str = ""):
        self.rates: dict[str, float] = dict(FALLBACK_RATES)
        self.last_updated: datetime | None = None
        self.is_live = False
        self.cloud_url = str(cloud_url or "").rstrip("/")
        self.cloud_api_key = str(cloud_api_key or "").strip()

    def fetch_rates(self) -> bool:
        """Try today's file cache first, then the cloud service API."""
        return self._load_cache() or self._fetch_live()

    def to_usd(self, amount: float, currency: str) -> float:
        if currency.upper() == "USD":
            return amount
        rate = self.rates.get(currency.upper())
        return (amount / rate) if rate else amount

    @property
    def usd_to_inr(self) -> float:
        return self.rates.get("INR", 84.5)

    @property
    def usd_to_eur(self) -> float:
        return self.rates.get("EUR", 0.92)

    def rate_display(self) -> str:
        src = "live" if self.is_live else "fallback"
        date_str = self.last_updated.strftime("%d %b %Y") if self.last_updated else "—"
        return f"1 USD = Rs. {self.usd_to_inr:.2f}  ({src}, {date_str})"

    # ── Cache ────────────────────────────────────────────────────────────
    def _load_cache(self) -> bool:
        try:
            if not _CACHE_FILE.exists():
                return False
            data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            if data.get("date") != str(date.today()):
                return False
            rates = data.get("rates", {})
            if not rates:
                return False
            self.rates = {**FALLBACK_RATES, **{k: float(v) for k, v in rates.items()}}
            self.rates["USD"] = 1.0
            fetched_at = data.get("fetched_at", "")
            self.last_updated = datetime.fromisoformat(fetched_at) if fetched_at else datetime.now()
            self.is_live = True
            return True
        except Exception:
            return False

    def _save_cache(self):
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "date": str(date.today()),
                "fetched_at": self.last_updated.isoformat() if self.last_updated else "",
                "rates": {k: v for k, v in self.rates.items() if k != "USD"},
            }
            _CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── Live fetch via cloud service ──────────────────────────────────────
    def _fetch_live(self) -> bool:
        if not self.cloud_url:
            self.is_live = False
            return False
        try:
            headers = {"x-api-key": self.cloud_api_key} if self.cloud_api_key else {}
            resp = requests.get(
                f"{self.cloud_url}/api/rates",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("rates", {})
            if rates:
                self.rates = {**FALLBACK_RATES, **{k: float(v) for k, v in rates.items()}}
                self.rates["USD"] = 1.0
                fetched_at = data.get("fetched_at", "")
                self.last_updated = datetime.fromisoformat(fetched_at) if fetched_at else datetime.now()
                self.is_live = True
                self._save_cache()
                return True
        except Exception:
            pass
        self.is_live = False
        return False
