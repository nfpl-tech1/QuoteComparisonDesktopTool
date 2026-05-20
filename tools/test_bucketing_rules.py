"""
Simple sanity checks for deterministic post-extraction rebucketing.

Run with:
    python tools/test_bucketing_rules.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.bucketing_rules import rebucket_charges


def _assert_bucket(label: str, quote_type: str, charge: dict, expected: str):
    result = rebucket_charges(quote_type, [charge])[0]
    actual = result.get("category")
    if actual != expected:
        raise AssertionError(
            f"{label} failed: expected {expected!r}, got {actual!r} for charge {result!r}"
        )
    print(f"PASS: {label} -> {actual}")


def main():
    _assert_bucket(
        "FCL B/L fee rebuckets to EXW",
        "fcl",
        {
            "category": "FCL (Ocean Freight)",
            "name_of_charge": "B/L Fee",
            "unit_of_measurement": "Per BL",
            "remarks": "",
        },
        "EXW / Origin Charges",
    )

    _assert_bucket(
        "FCL destination THC stays destination",
        "fcl",
        {
            "category": "FCL (Ocean Freight)",
            "name_of_charge": "THC",
            "unit_of_measurement": "Per Container (40ft HC)",
            "remarks": "destination thc at pod",
        },
        "Destination Charges",
    )

    _assert_bucket(
        "FCL origin THC moves to EXW",
        "fcl",
        {
            "category": "FCL (Ocean Freight)",
            "name_of_charge": "THC",
            "unit_of_measurement": "Per Container (40ft HC)",
            "remarks": "origin terminal handling at pol",
        },
        "EXW / Origin Charges",
    )

    _assert_bucket(
        "FCL freight surcharge stays in freight",
        "fcl",
        {
            "category": "EXW / Origin Charges",
            "name_of_charge": "BAF",
            "unit_of_measurement": "Per Container (40ft HC)",
            "remarks": "",
        },
        "FCL (Ocean Freight)",
    )

    _assert_bucket(
        "LCL destination CFS stays destination",
        "lcl",
        {
            "category": "Destination Charges",
            "name_of_charge": "Destination CFS",
            "unit_of_measurement": "Per CBM",
            "remarks": "destination cfs",
        },
        "Destination Charges",
    )

    _assert_bucket(
        "LCL destination THC moves out of freight",
        "lcl",
        {
            "category": "LCL (Ocean Freight)",
            "name_of_charge": "THC",
            "unit_of_measurement": "Per CBM",
            "remarks": "destination terminal handling",
        },
        "Destination Charges",
    )

    _assert_bucket(
        "Air origin trucking fuel stays origin",
        "air",
        {
            "category": "AF (Air Freight)",
            "name_of_charge": "Trucking Fuel Surcharge",
            "unit_of_measurement": "Per KG",
            "remarks": "origin trucking",
        },
        "EXW / Origin Charges",
    )

    print("\nAll bucketing checks passed.")


if __name__ == "__main__":
    main()
