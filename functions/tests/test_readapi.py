"""Tests for the read-API panels and query parsing."""

import datetime as dt

import pandas as pd
import pytest
from pydantic import ValidationError

from cost_readapi.panels import build_panel
from cost_readapi.params import parse_query

TODAY = dt.date(2026, 7, 16)

_COLUMNS = [
    "date",
    "subscription_id",
    "subscription_name",
    "resource_group",
    "service_name_raw",
    "business_category",
    "cost_actual",
    "cost_amortized",
    "currency",
]


def _sample():
    rows = [
        ("2026-07-01", "s1", "Prod", "rg-prod", "Microsoft.Compute", "Servers", 10.0, 10.0, "USD"),
        ("2026-07-08", "s1", "Prod", "rg-prod", "Microsoft.Compute", "Servers", 20.0, 20.0, "USD"),
        ("2026-07-08", "s1", "Prod", "rg-data", "Microsoft.Sql", "Databases", 5.0, 5.0, "USD"),
        ("2026-06-30", "s1", "Prod", "rg-prod", "Microsoft.Compute", "Servers", 7.0, 7.0, "USD"),
    ]
    return pd.DataFrame(rows, columns=_COLUMNS)


def test_parse_defaults():
    query = parse_query({})
    assert query.panel == "trend"
    assert query.range == "last_30"
    assert query.cost_type == "amortized"


def test_parse_invalid_panel_raises():
    with pytest.raises(ValidationError):
        parse_query({"panel": "nope"})


def test_by_category_totals():
    query = parse_query({"panel": "by_category", "range": "all"})
    result = build_panel(_sample(), query, today=TODAY)
    totals = {item["category"]: item["cost"] for item in result["items"]}
    assert totals["Servers"] == 37.0
    assert totals["Databases"] == 5.0


def test_kpis_month_to_date():
    query = parse_query({"panel": "kpis"})
    result = build_panel(_sample(), query, today=TODAY)
    assert result["mtd"] == 35.0
    assert result["prev_month_to_date"] == 0.0


def test_filter_by_category():
    query = parse_query({"panel": "by_resource_group", "range": "all", "category": "Servers"})
    result = build_panel(_sample(), query, today=TODAY)
    totals = {item["resource_group"]: item["cost"] for item in result["items"]}
    assert totals == {"rg-prod": 37.0}


def test_trend_weekly_sums_all_rows():
    query = parse_query({"panel": "trend", "range": "last_90", "granularity": "weekly"})
    result = build_panel(_sample(), query, today=TODAY)
    assert result["granularity"] == "weekly"
    assert round(sum(point["cost"] for point in result["series"]), 2) == 42.0


def test_changes_week_over_week():
    query = parse_query({"panel": "changes"})
    result = build_panel(_sample(), query, today=TODAY)
    totals = {item["category"]: item for item in result["items"]}
    assert totals["Servers"]["last_week"] == 20.0
    assert totals["Servers"]["this_week"] == 0.0


def test_email_summary_is_human_readable():
    query = parse_query({"panel": "email_summary"})
    result = build_panel(_sample(), query, today=TODAY)
    assert set(result) == {"subject", "text", "html"}
    assert "Servers" in result["text"]
    assert "$" in result["subject"]
    assert "<table" in result["html"]


def test_email_summary_includes_budget_context():
    query = parse_query({"panel": "email_summary", "budget": "40"})
    result = build_panel(_sample(), query, today=TODAY)
    # MTD is 35 of a 40 budget -> ~88%, crossing the 80% threshold.
    assert "% of your $40 monthly budget" in result["text"]
    assert "80% threshold" in result["text"]
    assert "of budget" in result["subject"]


def test_trend_includes_budget_line():
    query = parse_query(
        {"panel": "trend", "range": "all", "granularity": "monthly", "budget": "1000"}
    )
    result = build_panel(_sample(), query, today=TODAY)
    assert result["cumulative"] is False
    assert all(point["budget"] == 1000.0 for point in result["series"])


def test_trend_this_month_is_cumulative():
    query = parse_query({"panel": "trend", "range": "this_month", "budget": "50"})
    result = build_panel(_sample(), query, today=TODAY)
    assert result["cumulative"] is True
    costs = [point["cost"] for point in result["series"]]
    # Running total over the month to date: Jul 1 (10) then Jul 8 (+25) = 35.
    assert costs == sorted(costs)
    assert costs[-1] == 35.0
    assert all(point["budget"] == 50.0 for point in result["series"])


def test_budget_status_flags_breaches():
    query = parse_query({"panel": "budget_status", "budget": "30"})
    result = build_panel(_sample(), query, today=TODAY)
    statuses = {item["threshold"]: item["status"] for item in result["items"]}
    assert statuses["100%"] == "Breached"
    assert result["used_pct"] > 100


def test_empty_frame_is_safe():
    empty = pd.DataFrame(columns=_COLUMNS)
    result = build_panel(empty, parse_query({"panel": "kpis"}), today=TODAY)
    assert result["mtd"] == 0.0
