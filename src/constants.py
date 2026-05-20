AIR_BUCKETS = [
    "EXW / Origin Charges",
    "AF (Air Freight)",
    "Destination Charges",
]

FCL_BUCKETS = [
    "EXW / Origin Charges",
    "FCL (Ocean Freight)",
    "Destination Charges",
]

LCL_BUCKETS = [
    "EXW / Origin Charges",
    "LCL (Ocean Freight)",
    "Destination Charges",
]

# Backwards-compatibility alias used by existing comparison/mapping pages
AIR_IMPORT_BUCKETS = AIR_BUCKETS

CONTAINER_TYPES = ["20ft GP", "40ft GP", "40ft HC"]

QUOTE_TYPES = ["air", "fcl", "lcl"]

CURRENCIES = [
    "USD", "EUR", "GBP", "INR", "AED", "SGD", "CNY", "JPY",
    "AUD", "CAD", "THB", "MYR", "HKD", "CHF", "KRW",
]

UNITS_OF_MEASUREMENT = [
    "Per Container (20ft)",
    "Per Container (40ft)",
    "Per Container (40ft HC)",
    "Per BL",
    "Per Shipment",
    "Per KG",
    "Per CBM",
    "Per Ton",
    "Lumpsum",
    "Per Document",
    "Per AWB",
    "Per Pallet",
    "Per Hour",
    "Per Day",
    "Per Set",
]

APP_COLORS = {
    "sidebar_bg": "#1E2A3A",
    "sidebar_active": "#1976D2",
    "sidebar_done": "#27AE60",
    "sidebar_text": "#B0BEC5",
    "sidebar_text_active": "#FFFFFF",
    "primary": "#1976D2",
    "primary_dark": "#1565C0",
    "success": "#27AE60",
    "error": "#E53935",
    "warning": "#F57C00",
    "bg": "#F0F4F8",
    "card": "#FFFFFF",
    "border": "#DCE3EA",
    "text": "#1E2A3A",
    "text_muted": "#607080",
    "cheapest": "#C8E6C9",
    "cheapest_text": "#1B5E20",
}
