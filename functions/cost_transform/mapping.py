"""Service-to-business-category mapping (the semantic layer)."""

from __future__ import annotations

import json
from importlib import resources

_DEFAULT_CATEGORY = "Other"


def load_mapping() -> dict[str, str]:
    """Load the service-to-category mapping, keyed by lower-cased service name."""
    text = resources.files("cost_transform").joinpath("mapping.json").read_text(encoding="utf-8")
    raw: dict[str, str] = json.loads(text)
    return {key.lower(): value for key, value in raw.items()}


def map_service(service_name_raw: str, mapping: dict[str, str]) -> str:
    """Map a raw Azure service name to its business category.

    Args:
        service_name_raw: The raw service identifier (e.g. "Microsoft.Compute").
        mapping: Lower-cased service-to-category lookup from load_mapping.

    Returns:
        The business category, or "Other" when the service is unmapped.
    """
    return mapping.get(service_name_raw.strip().lower(), _DEFAULT_CATEGORY)
