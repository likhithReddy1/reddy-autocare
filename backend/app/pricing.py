import re

DOORSTEP_CHARGE_PAISE = 9900

_CATEGORY_ALIASES = {
    "bike": "Bike / Scooter",
    "bike scooter": "Bike / Scooter",
    "scooter": "Bike / Scooter",
    "motorcycle": "Bike / Scooter",
    "two wheeler": "Bike / Scooter",
    "hatchback": "Hatchback",
    "sedan": "Sedan",
    "suv": "SUV / MUV",
    "muv": "SUV / MUV",
    "suv muv": "SUV / MUV",
    "luxury suv": "Luxury / Large SUV",
    "large suv": "Luxury / Large SUV",
    "luxury large suv": "Luxury / Large SUV",
}


def canonical_vehicle_category(vehicle_type: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", vehicle_type.lower()).strip()
    return _CATEGORY_ALIASES.get(normalized)
