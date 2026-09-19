"""Transform raw Cost Management exports into curated Parquet."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO

import pandas as pd

from .config import Settings
from .mapping import map_service
from .storage import BlobInfo, BlobStore

logger = logging.getLogger(__name__)

CANONICAL_COLUMNS = [
    "date",
    "subscription_id",
    "subscription_name",
    "resource_group",
    "service_name_raw",
    "business_category",
    "cost_actual",
    "cost_amortized",
    "currency",
    "period",
]

_SOURCE_COLUMNS: dict[str, list[str]] = {
    "date": ["Date", "UsageDate", "BillingMonth"],
    "subscription_id": ["SubscriptionId", "SubscriptionGuid"],
    "subscription_name": ["SubscriptionName"],
    "resource_group": ["ResourceGroup", "ResourceGroupName"],
    "service_name_raw": ["ConsumedService", "MeterCategory", "ServiceName"],
    "cost": ["CostInBillingCurrency", "Cost", "PreTaxCost", "CostInUSD"],
    "currency": ["BillingCurrencyCode", "BillingCurrency", "Currency"],
}
_REQUIRED = ("date", "service_name_raw", "cost")


@dataclass
class TransformResult:
    """Outcome of a transform run."""

    processed: bool
    reason: str
    rows: int = 0
    periods: list[str] = field(default_factory=list)


def _first_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first candidate column present in df (case-insensitive)."""
    lower = {str(c).lower(): str(c) for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _series_or_blank(df: pd.DataFrame, column: str | None) -> pd.Series:
    """Return the named column as strings, or an all-empty series."""
    if column is None:
        return pd.Series([""] * len(df))
    return df[column].astype(str)


def _canonicalise(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Map source export columns onto the canonical curated schema."""
    resolved = {key: _first_col(df, cands) for key, cands in _SOURCE_COLUMNS.items()}
    missing = [key for key in _REQUIRED if resolved[key] is None]
    if missing:
        message = f"export missing required column(s): {missing}"
        raise ValueError(message)

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[resolved["date"]]).dt.strftime("%Y-%m-%d")
    out["subscription_id"] = _series_or_blank(df, resolved["subscription_id"])
    out["subscription_name"] = _series_or_blank(df, resolved["subscription_name"])
    out["resource_group"] = _series_or_blank(df, resolved["resource_group"])
    out["service_name_raw"] = _series_or_blank(df, resolved["service_name_raw"])
    out["business_category"] = out["service_name_raw"].map(lambda s: map_service(s, mapping))
    cost = pd.to_numeric(df[resolved["cost"]], errors="coerce").fillna(0.0)
    out["cost_amortized"] = cost
    out["cost_actual"] = cost
    out["currency"] = _series_or_blank(df, resolved["currency"])
    out["period"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m")
    return out[CANONICAL_COLUMNS]


def _latest_export(store: BlobStore, container: str, prefix: str) -> BlobInfo | None:
    """Return the most recently modified CSV export blob, or None."""
    blobs = [b for b in store.list_blobs(container, prefix) if b.name.lower().endswith(".csv")]
    if not blobs:
        return None
    return max(blobs, key=lambda b: b.last_modified)


def run_transform(store: BlobStore, settings: Settings, mapping: dict[str, str]) -> TransformResult:
    """Read the latest raw export, map categories, and write curated Parquet by period.

    Skips work when there is no export, or no new export since the last run
    (idempotent guard). Writes one Parquet blob per billing period, overwriting
    that period so cost restatements replace rather than duplicate.

    Args:
        store: Blob storage abstraction.
        settings: Container and prefix configuration.
        mapping: Service-to-category lookup.

    Returns:
        A TransformResult describing what happened.
    """
    latest = _latest_export(store, settings.raw_container, settings.raw_prefix)
    if latest is None:
        logger.info("no export files found under %s", settings.raw_prefix)
        return TransformResult(processed=False, reason="no export files")

    watermark = latest.last_modified.isoformat()
    if store.read_text(settings.curated_container, settings.watermark_blob) == watermark:
        logger.info("no new export since last run")
        return TransformResult(processed=False, reason="no new export")

    raw_bytes = store.read_blob(settings.raw_container, latest.name)
    frame = _canonicalise(pd.read_csv(BytesIO(raw_bytes)), mapping)

    periods: list[str] = []
    for period, group in frame.groupby("period"):
        buffer = BytesIO()
        group.drop(columns=["period"]).to_parquet(buffer, index=False)
        blob_name = f"{settings.curated_prefix}/period={period}/data.parquet"
        store.write_blob(settings.curated_container, blob_name, buffer.getvalue())
        periods.append(str(period))

    store.write_text(settings.curated_container, settings.watermark_blob, watermark)
    logger.info("transformed %d rows across %d period(s)", len(frame), len(periods))
    return TransformResult(processed=True, reason="ok", rows=len(frame), periods=sorted(periods))
