from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChargeRow:
    category: str = ""
    name_of_charge: str = ""
    currency: str = "USD"
    unit_of_measurement: str = ""
    rate: float = 0.0
    remarks: str = ""
    if_applicable: bool = False  # True for optional/conditional charges

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "name_of_charge": self.name_of_charge,
            "currency": self.currency,
            "unit_of_measurement": self.unit_of_measurement,
            "rate": self.rate,
            "remarks": self.remarks,
            "if_applicable": self.if_applicable,
        }

    @staticmethod
    def from_dict(d: dict) -> "ChargeRow":
        try:
            rate = float(d.get("rate") or 0)
        except (ValueError, TypeError):
            rate = 0.0
        return ChargeRow(
            category=str(d.get("category") or ""),
            name_of_charge=str(d.get("name_of_charge") or ""),
            currency=str(d.get("currency") or "USD"),
            unit_of_measurement=str(d.get("unit_of_measurement") or ""),
            rate=rate,
            remarks=str(d.get("remarks") or ""),
            if_applicable=bool(d.get("if_applicable", False)),
        )


class VendorData:
    def __init__(self, vendor_name: str, source_file: str):
        self.vendor_name = vendor_name
        self.source_file = source_file
        self.charges: list[ChargeRow] = []
        self.status: str = "pending"   # pending | processing | done | error
        self.error: str = ""
        self.quote_type: str = "air"        # "air" | "fcl" | "lcl"
        self.shipping_line: str = ""        # FCL only, e.g. "Maersk"
        self.airline: str = ""              # Air only, e.g. "Air India (AI)"
        self.container_type: str = ""       # FCL only, e.g. "40ft GP"
        self.etd: str = ""                  # Estimated Time of Departure (date string)
        self.transit_days: str = ""         # e.g. "21 days", "25-30 days"
        self.free_days_origin: int = 0      # free days at origin port
        self.free_days_destination: int = 0 # free days at destination port

    @property
    def uid(self) -> str:
        """Unique key for app.vendors dict — one entry per mode/shipping-line/container-type/airline."""
        if self.shipping_line:
            ct = f"|{self.container_type}" if self.container_type else ""
            return f"{self.source_file}|{self.quote_type}|{self.shipping_line}{ct}"
        if self.airline:
            return f"{self.source_file}|{self.quote_type}|{self.airline}"
        return f"{self.source_file}|{self.quote_type}"

    def set_charges_from_dicts(self, charges: list[dict]):
        self.charges = [ChargeRow.from_dict(c) for c in charges]

    def to_charge_dicts(self) -> list[dict]:
        return [c.to_dict() for c in self.charges]

    def to_dict(self) -> dict:
        return {
            "vendor_name": self.vendor_name,
            "source_file": self.source_file,
            "quote_type": self.quote_type,
            "airline": self.airline,
            "shipping_line": self.shipping_line,
            "container_type": self.container_type,
            "etd": self.etd,
            "transit_days": self.transit_days,
            "free_days_origin": self.free_days_origin,
            "free_days_destination": self.free_days_destination,
            "charges": self.to_charge_dicts(),
        }

    @staticmethod
    def from_dict(d: dict) -> "VendorData":
        vd = VendorData(d.get("vendor_name", ""), d.get("source_file", ""))
        vd.quote_type = d.get("quote_type", "air")
        vd.airline = d.get("airline", "")
        vd.shipping_line = d.get("shipping_line", "")
        vd.container_type = d.get("container_type", "")
        vd.etd = str(d.get("etd") or "")
        vd.transit_days = str(d.get("transit_days") or "")
        try:
            vd.free_days_origin = int(d.get("free_days_origin") or 0)
        except (ValueError, TypeError):
            vd.free_days_origin = 0
        try:
            vd.free_days_destination = int(d.get("free_days_destination") or 0)
        except (ValueError, TypeError):
            vd.free_days_destination = 0
        vd.set_charges_from_dicts(d.get("charges", []))
        vd.status = "done"
        return vd
