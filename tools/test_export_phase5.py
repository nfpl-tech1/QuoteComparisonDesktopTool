"""
Simple test for Phase 5 export changes.
Run this with a GUI available (PySide6) to allow widget creation.
"""
import os
import tempfile
import pprint

from PySide6.QtWidgets import QApplication

from src.models.vendor_data import VendorData, ChargeRow
from src.pages.comparison_page import ComparisonPage


class DummyCurrencyService:
    def __init__(self):
        self.usd_to_inr = 83.0
        self.is_live = False
        self.last_updated = None

    def to_usd(self, rate, currency):
        # For testing assume provided rates are already in USD
        return float(rate or 0.0)

    def rate_display(self):
        return "Fallback rates"

    def fetch_rates(self):
        return True


class DummyApp:
    def __init__(self):
        self.vendors = {}
        self.currency_service = DummyCurrencyService()


def make_vendor(name, src, shipping_line=None):
    vd = VendorData(name, src)
    vd.quote_type = "fcl"
    if shipping_line:
        vd.shipping_line = shipping_line
    # add a simple container / freight charge
    vd.charges.append(ChargeRow(category="FCL (Ocean Freight)",
                                name_of_charge="Ocean Freight",
                                currency="USD", unit_of_measurement="Per Container (40ft)",
                                rate=1200.0))
    vd.charges.append(ChargeRow(category="Destination Charges",
                                name_of_charge="THC",
                                currency="USD", unit_of_measurement="", rate=150.0))
    return vd


def main():
    app = QApplication([])
    dummy = DummyApp()

    # Create two vendors under same vendor name but different shipping lines
    v1 = make_vendor("ACE Freight", "ace_maersk.msg", shipping_line="Maersk")
    v2 = make_vendor("ACE Freight", "ace_msc.msg", shipping_line="MSC")
    # Another vendor single-line
    v3 = make_vendor("IFF Logistics", "iff.msg", shipping_line=None)

    # Add to dummy app in insertion order
    dummy.vendors[v1.uid] = v1
    dummy.vendors[v2.uid] = v2
    dummy.vendors[v3.uid] = v3

    page = ComparisonPage(dummy)
    page._current_mode = "fcl"
    page._build_table()

    out_dir = os.path.join(tempfile.gettempdir(), "qc_export_test")
    os.makedirs(out_dir, exist_ok=True)
    xl_path = os.path.join(out_dir, "qc_test.xlsx")
    csv_path = os.path.join(out_dir, "qc_test.csv")

    print("Exporting to:", xl_path, csv_path)
    page._export_excel_to_path(xl_path)
    page._export_csv_to_path(csv_path)

    # Inspect written files
    print("Files written:")
    for p in (xl_path, csv_path):
        print(" -", p, os.path.exists(p), os.path.getsize(p) if os.path.exists(p) else 0)

    # Check merged cells in excel
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xl_path, read_only=True)
        ws = wb.active
        merges = list(ws.merged_cells.ranges)
        print("Merged ranges:")
        pprint.pprint(merges)
    except Exception as exc:
        print("Could not inspect Excel:", exc)

    # Read CSV head
    import csv
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        rows = [next(r) for _ in range(4)]
    print("CSV preview (first 4 rows):")
    pprint.pprint(rows)


if __name__ == "__main__":
    main()
