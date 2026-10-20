"""The published rate card (spec 4.2 #5: prices come only from the rate card).

Prices are per category + line. The agent and technician may only quote a number
that appears here; anything else is blocked by rules.protective.price_on_card.
Amounts in INR. This mirrors the examples in the journey pages (J4, J6, J9).
"""
from __future__ import annotations

# category -> { line_code: {"label": str, "price": float} }
RATE_CARD: dict[str, dict[str, dict]] = {
    "AC": {
        "install_split": {"label": "Split AC installation", "price": 1500.0},
        "visit_fee": {"label": "Inspection / visit charge", "price": 299.0},
        "gas_refill": {"label": "Gas refill", "price": 2200.0},
        "leak_repair": {"label": "Leak repair", "price": 850.0},
        "copper_pipe_per_m": {"label": "Copper pipe (per m)", "price": 350.0},
        "service": {"label": "AC service", "price": 499.0},
        "care_plan_1y": {"label": "Care plan 1 year (2 services + repairs)", "price": 1999.0},
    },
    "TV": {
        "wall_mount": {"label": "TV wall mount", "price": 700.0},
        "visit_fee": {"label": "Inspection / visit charge", "price": 299.0},
    },
    "WASHER": {
        "install": {"label": "Washing machine installation", "price": 700.0},
        "visit_fee": {"label": "Inspection / visit charge", "price": 299.0},
        "drain_pump": {"label": "Drain pump replacement", "price": 1200.0},
    },
    "PHONE": {
        "screen_replace": {"label": "Screen replacement", "price": 6400.0},
        "visit_fee": {"label": "Inspection / visit charge", "price": 299.0},
    },
    "MOVE": {
        "uninstall": {"label": "Uninstall (per machine)", "price": 600.0},
        "install": {"label": "Install (per machine)", "price": 900.0},
    },
}


def _card() -> dict:
    """Admin-editable at runtime; falls back to the RATE_CARD module default."""
    try:
        from app.admin import config

        return config.get("rate_card") or RATE_CARD
    except Exception:  # noqa: BLE001  (e.g. during import before config loads)
        return RATE_CARD


def lookup(category: str, line: str) -> dict | None:
    return _card().get(category.upper(), {}).get(line)


def price_of(category: str, line: str) -> float | None:
    item = lookup(category, line)
    return item["price"] if item else None


def all_prices(category: str) -> set[float]:
    """Every valid price for a category (used to validate off-card amounts)."""
    return {v["price"] for v in _card().get(category.upper(), {}).values()}
