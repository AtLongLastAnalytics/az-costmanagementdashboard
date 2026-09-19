"""Tests for the weekly report composition."""

import datetime as dt

import pandas as pd

from cost_report.compose import build_weekly_email

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
    ]
    return pd.DataFrame(rows, columns=_COLUMNS)


def test_weekly_email_has_fields():
    result = build_weekly_email(_sample(), today=TODAY)
    assert set(result) == {"subject", "text", "html"}
    assert "Weekly" in result["subject"]
    assert "movers" in result["text"].lower()
    assert "<table" in result["html"]


def test_weekly_email_empty_is_safe():
    result = build_weekly_email(pd.DataFrame(columns=_COLUMNS), today=TODAY)
    assert "subject" in result


def test_weekly_email_shows_budget_and_coloured_movers():
    result = build_weekly_email(_sample(), today=TODAY, budget=40)
    assert "Budget $40" in result["text"]
    assert "of budget" in result["text"]
    # Week-over-week movers render as colour-coded percentage spans.
    assert "<span style='color:#" in result["html"]
