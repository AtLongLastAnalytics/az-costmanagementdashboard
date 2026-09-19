"""Tests for the transform: mapping applied, restatement, and the guard."""

from datetime import UTC, datetime
from io import BytesIO

import pandas as pd

from cost_transform.transform import run_transform

RAW = "raw"
CURATED = "curated"
PREFIX = "cost-exports"
EXPORT = f"{PREFIX}/2026/data.csv"


def _read_curated(store, period):
    data = store.read_blob(CURATED, f"cost/period={period}/data.parquet")
    return pd.read_parquet(BytesIO(data))


def test_transforms_and_writes_curated(store, settings, mapping, sample_csv):
    store.add(RAW, EXPORT, sample_csv, datetime(2026, 7, 3, tzinfo=UTC))

    result = run_transform(store, settings, mapping)

    assert result.processed
    assert result.rows == 3
    assert result.periods == ["2026-07"]

    df = _read_curated(store, "2026-07")
    assert set(df["business_category"]) == {"Servers", "Storage", "Databases"}
    assert "period" not in df.columns
    assert list(df["currency"].unique()) == ["USD"]


def test_guard_skips_when_no_files(store, settings, mapping):
    result = run_transform(store, settings, mapping)

    assert not result.processed
    assert result.reason == "no export files"


def test_guard_skips_when_no_new_export(store, settings, mapping, sample_csv):
    store.add(RAW, EXPORT, sample_csv, datetime(2026, 7, 3, tzinfo=UTC))
    run_transform(store, settings, mapping)

    result = run_transform(store, settings, mapping)

    assert not result.processed
    assert result.reason == "no new export"


def test_restatement_overwrites_period(store, settings, mapping, sample_csv):
    store.add(RAW, EXPORT, sample_csv, datetime(2026, 7, 3, tzinfo=UTC))
    run_transform(store, settings, mapping)

    restated = (
        b"Date,SubscriptionId,ConsumedService,CostInBillingCurrency,BillingCurrencyCode\n"
        b"2026-07-05,sub-1,Microsoft.Compute,99.0,USD\n"
    )
    store.add(RAW, EXPORT, restated, datetime(2026, 7, 6, tzinfo=UTC))

    result = run_transform(store, settings, mapping)

    assert result.processed
    df = _read_curated(store, "2026-07")
    assert len(df) == 1
    assert float(df["cost_amortized"].iloc[0]) == 99.0


def test_missing_required_column_raises(store, settings, mapping):
    bad = b"Foo,Bar\n1,2\n"
    store.add(RAW, EXPORT, bad, datetime(2026, 7, 3, tzinfo=UTC))

    try:
        run_transform(store, settings, mapping)
    except ValueError as exc:
        assert "required column" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing columns")
