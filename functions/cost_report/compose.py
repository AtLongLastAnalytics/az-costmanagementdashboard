"""Compose the branded weekly cost report email from curated data."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd

from cost_readapi.emailfmt import BRAND, delta_html, table, wrap_email
from cost_readapi.panels import build_panel
from cost_readapi.params import Query


def build_weekly_email(
    df: pd.DataFrame, today: dt.date | None = None, budget: float | None = None
) -> dict[str, Any]:
    """Build the weekly report email (subject/text/html).

    Combines the month-to-date summary, category breakdown, and week-over-week
    movers, reusing the read-API panels so the numbers match the dashboard, and
    the shared branded email theme.

    Args:
        df: Curated cost rows.
        today: Reference date (defaults to the current date).
        budget: Monthly budget for the budget-vs-forecast line (optional).

    Returns:
        A dict with subject, text, and html.
    """
    today = today or dt.date.today()
    kpis = build_panel(df, Query(panel="kpis"), today)
    cats = build_panel(df, Query(panel="by_category", range="this_month"), today)
    changes = build_panel(df, Query(panel="changes"), today)

    # Show every category so the rows reconcile to the month-to-date total.
    categories = cats.get("items", [])
    movers = changes.get("items", [])[:5]

    headline = (
        f"Month-to-date: ${kpis['mtd']:,.2f} "
        f"(forecast ${kpis['forecast']:,.2f}, {kpis['change_pct']:+.1f}% vs last month)"
    )
    budget_line = ""
    if budget:
        pct = kpis["forecast"] / budget * 100
        state = "over" if kpis["forecast"] > budget else "within"
        budget_line = f"Budget ${budget:,.0f}/mo — forecast is {pct:.0f}% of budget ({state})."

    cat_lines = [f"{i['category']}: ${i['cost']:,.2f}" for i in categories]
    mover_lines = [
        f"{m['category']}: ${m['last_week']:,.2f} -> "
        f"${m['this_week']:,.2f} ({m['delta_pct']:+.1f}%)"
        for m in movers
    ]
    text = (
        f"{headline}\n"
        + (f"{budget_line}\n" if budget_line else "")
        + "\nBy category:\n"
        + "\n".join(cat_lines)
        + "\n\nWeek-over-week movers:\n"
        + ("\n".join(mover_lines) if mover_lines else "No week-over-week changes.")
        + f"\n\n- {BRAND}"
    )

    cat_rows = [[str(i["category"]), f"${i['cost']:,.2f}"] for i in categories]
    mover_rows = [
        [
            str(m["category"]),
            f"${m['last_week']:,.2f}",
            f"${m['this_week']:,.2f}",
            delta_html(m["delta_pct"]),
        ]
        for m in movers
    ]
    budget_html = f"<p style='color:#6b7280'>{budget_line}</p>" if budget_line else ""
    body = (
        f"<p style='font-size:18px'><strong>{headline}</strong></p>"
        + budget_html
        + "<h3>By category</h3>"
        + table(["Category", "Cost"], cat_rows)
        + "<h3>Week-over-week movers</h3>"
        + table(["Category", "Last week", "This week", "Change"], mover_rows)
    )
    return {
        "subject": f"Weekly Azure cost report — {today:%d %b %Y}",
        "text": text,
        "html": wrap_email("Weekly Azure cost report", body),
    }
