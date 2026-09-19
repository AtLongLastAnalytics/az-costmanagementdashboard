"""Tests for the curated Parquet loader."""

from datetime import UTC, datetime
from io import BytesIO

import pandas as pd

from cost_readapi.loader import load_curated


def test_load_curated_concatenates(store):
    frame = pd.DataFrame(
        [{"date": "2026-07-01", "business_category": "Servers", "cost_amortized": 1.0}]
    )
    buffer = BytesIO()
    frame.to_parquet(buffer, index=False)
    store.add(
        "curated",
        "cost/period=2026-07/data.parquet",
        buffer.getvalue(),
        datetime(2026, 7, 16, tzinfo=UTC),
    )

    out = load_curated(store, "curated", "cost")

    assert len(out) == 1
    assert out.iloc[0]["business_category"] == "Servers"


def test_load_curated_empty_returns_typed_frame(store):
    out = load_curated(store, "curated", "cost")
    assert out.empty
    assert "business_category" in out.columns
