from __future__ import annotations


def normalize_location(state: str, district: str, village_or_ward: str | None = None) -> dict:
    return {
        "state": state.strip().title(),
        "district": district.strip().title(),
        "village_or_ward": village_or_ward.strip().title() if village_or_ward else None,
    }
