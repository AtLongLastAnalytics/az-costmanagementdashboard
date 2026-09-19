"""Panel aggregations for the read API (grouping, deltas, bucketing)."""

from __future__ import annotations

import calendar
import datetime as dt
from typing import Any, cast

import pandas as pd

from .emailfmt import BRAND, table, wrap_email
from .params import Query


def _cost_column(cost_type: str) -> str:
    return "cost_actual" if cost_type == "actual" else "cost_amortized"


def _days_in_month(day: dt.date) -> int:
    return calendar.monthrange(day.year, day.month)[1]


def _apply_filters(df: pd.DataFrame, query: Query) -> pd.DataFrame:
    out = df
    if query.subscription:
        out = out[out["subscription_id"] == query.subscription]
    if query.resource_group:
        out = out[out["resource_group"] == query.resource_group]
    if query.category:
        out = out[out["business_category"] == query.category]
    return out


def _date_window(range_: str, today: dt.date) -> tuple[dt.date | None, dt.date | None]:
    if range_ in ("this_month", "mtd"):
        return today.replace(day=1), today
    if range_ == "last_7":
        return today - dt.timedelta(days=6), today
    if range_ == "last_30":
        return today - dt.timedelta(days=29), today
    if range_ == "last_90":
        return today - dt.timedelta(days=89), today
    return None, None


def _bucket_labels(dates: pd.Series, granularity: str) -> pd.Series:
    parsed = pd.to_datetime(dates)
    if granularity == "monthly":
        return parsed.dt.strftime("%Y-%m")
    if granularity == "weekly":
        monday = parsed - pd.to_timedelta(parsed.dt.dayofweek, unit="D")
        return monday.dt.strftime("%Y-%m-%d")
    return parsed.dt.strftime("%Y-%m-%d")


def _trend(
    data: pd.DataFrame,
    cost: str,
    granularity: str,
    budget: float | None = None,
    cumulative: bool = False,
) -> dict[str, Any]:
    """Build a trend series.

    When ``cumulative`` is set (the current-month view), ``cost`` is a running
    total so the line climbs toward the budget and its threshold crossings are
    visible. Otherwise each point is that bucket's own spend.
    """
    if data.empty:
        return {"granularity": granularity, "series": [], "cumulative": cumulative}
    tmp = data.copy()
    tmp["_bucket"] = _bucket_labels(tmp["date"], granularity)
    grouped = tmp.groupby("_bucket")[cost].sum().reset_index().sort_values("_bucket")
    series = []
    running = 0.0
    for bucket, value in zip(grouped["_bucket"], grouped[cost], strict=False):
        running += float(value)
        amount = running if cumulative else float(value)
        point = {"bucket": str(bucket), "cost": round(amount, 2)}
        if budget is not None:
            point["budget"] = round(float(budget), 2)
        series.append(point)
    return {"granularity": granularity, "series": series, "cumulative": cumulative}


def _budget_status(
    data: pd.DataFrame, cost: str, today: dt.date, budget: float | None
) -> dict[str, Any]:
    total = float(budget) if budget else 0.0
    if data.empty or not total:
        return {"mtd": 0.0, "budget": round(total, 2), "used_pct": 0.0, "items": []}
    month_start = today.replace(day=1)
    mtd = float(data.loc[(data["_d"] >= month_start) & (data["_d"] <= today), cost].sum())
    items = [
        {
            "threshold": f"{pct}%",
            "amount": round(total * pct / 100, 2),
            "status": "Breached" if mtd >= total * pct / 100 else "OK",
        }
        for pct in (50, 80, 100)
    ]
    return {
        "mtd": round(mtd, 2),
        "budget": round(total, 2),
        "used_pct": round(mtd / total * 100, 1),
        "items": items,
    }


def _breakdown(data: pd.DataFrame, cost: str, column: str, label: str) -> dict[str, Any]:
    if data.empty:
        return {"items": []}
    grouped = data.groupby(column)[cost].sum().reset_index().sort_values(cost, ascending=False)
    items = [
        {label: str(name), "cost": round(float(c), 2)}
        for name, c in zip(grouped[column], grouped[cost], strict=False)
    ]
    return {"items": items}


def _kpis(data: pd.DataFrame, cost: str, today: dt.date) -> dict[str, Any]:
    if data.empty:
        return {"mtd": 0.0, "forecast": 0.0, "prev_month_to_date": 0.0, "change_pct": 0.0}
    month_start = today.replace(day=1)
    mtd = float(data.loc[(data["_d"] >= month_start) & (data["_d"] <= today), cost].sum())

    prev_month_end = month_start - dt.timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    prev_day = min(today.day, _days_in_month(prev_month_start))
    prev_cutoff = prev_month_start.replace(day=prev_day)
    prev = float(
        data.loc[(data["_d"] >= prev_month_start) & (data["_d"] <= prev_cutoff), cost].sum()
    )

    forecast = mtd / today.day * _days_in_month(month_start) if today.day else mtd
    change_pct = ((mtd - prev) / prev * 100) if prev else 0.0
    return {
        "mtd": round(mtd, 2),
        "forecast": round(forecast, 2),
        "prev_month_to_date": round(prev, 2),
        "change_pct": round(change_pct, 1),
    }


def _changes(data: pd.DataFrame, cost: str, today: dt.date) -> dict[str, Any]:
    if data.empty:
        return {"items": []}
    this_start = today - dt.timedelta(days=6)
    last_start = today - dt.timedelta(days=13)
    last_end = today - dt.timedelta(days=7)
    this = (
        data[(data["_d"] >= this_start) & (data["_d"] <= today)]
        .groupby("business_category")[cost]
        .sum()
    )
    last = (
        data[(data["_d"] >= last_start) & (data["_d"] <= last_end)]
        .groupby("business_category")[cost]
        .sum()
    )

    items = []
    for category in sorted(set(this.index) | set(last.index)):
        this_val = float(this.get(category, 0.0))
        last_val = float(last.get(category, 0.0))
        delta = ((this_val - last_val) / last_val * 100) if last_val else 0.0
        items.append(
            {
                "category": str(category),
                "last_week": round(last_val, 2),
                "this_week": round(this_val, 2),
                "delta_pct": round(delta, 1),
            }
        )
    items.sort(key=lambda row: abs(cast(float, row["delta_pct"])), reverse=True)
    return {"items": items}


def _budget_context(total: float, forecast: float, budget: float | None) -> str:
    """One sentence putting spend in budget terms (threshold crossed + forecast).

    Falls back to a generic line when no budget is supplied.
    """
    if not budget:
        return "Your Azure spend has crossed a budget threshold."
    used = total / budget * 100
    crossed = max((pct for pct in (50, 80, 100) if used >= pct), default=0)
    lead = f"You've used {used:.0f}% of your ${budget:,.0f} monthly budget"
    lead += f" — crossed the {crossed}% threshold." if crossed else "."
    over = forecast - budget
    if over > 0:
        return f"{lead} Forecast ${forecast:,.0f} for the month, about ${over:,.0f} over budget."
    return f"{lead} Forecast ${forecast:,.0f} for the month, within budget."


def _email_summary(
    data: pd.DataFrame, cost: str, today: dt.date, budget: float | None = None
) -> dict[str, Any]:
    """Build a ready-to-send, human-readable alert email (subject/text/html)."""
    if data.empty:
        return {
            "subject": "Azure cost alert",
            "text": f"No cost data is available yet.\n\n- {BRAND}",
            "html": wrap_email("Azure cost alert", "<p>No cost data is available yet.</p>"),
        }
    month_start = today.replace(day=1)
    month = data[(data["_d"] >= month_start) & (data["_d"] <= today)]
    total = float(month[cost].sum())
    by_cat = month.groupby("business_category")[cost].sum().sort_values(ascending=False).head(5)

    forecast = total / today.day * _days_in_month(month_start) if today.day else total
    context = _budget_context(total, forecast, budget)

    lines = [f"{category}: ${amount:,.2f}" for category, amount in by_cat.items()]
    text = (
        f"{context}\n\n"
        f"Month-to-date total: ${total:,.2f}\n\n"
        "Top categories:\n" + "\n".join(lines) + f"\n\n- {BRAND}"
    )
    rows = [[str(category), f"${amount:,.2f}"] for category, amount in by_cat.items()]
    body = (
        f"<p>{context}</p>"
        f"<p style='font-size:18px'><strong>Month-to-date total: ${total:,.2f}</strong></p>"
        + table(["Top categories", "Cost"], rows)
    )
    used_suffix = f" ({total / budget * 100:.0f}% of budget)" if budget else ""
    return {
        "subject": f"Azure cost alert — ${total:,.2f} month-to-date{used_suffix}",
        "text": text,
        "html": wrap_email("Azure cost alert", body),
    }


def build_panel(df: pd.DataFrame, query: Query, today: dt.date | None = None) -> dict[str, Any]:
    """Build the requested dashboard panel from curated data.

    Args:
        df: Curated cost rows.
        query: Validated query parameters.
        today: Reference date (defaults to the current date).

    Returns:
        A JSON-serialisable dict shaped for the requested panel.
    """
    today = today or dt.date.today()
    cost = _cost_column(query.cost_type)
    data = _apply_filters(df, query).copy()
    if not data.empty:
        data["_d"] = pd.to_datetime(data["date"]).dt.date

    if query.panel == "kpis":
        return _kpis(data, cost, today)
    if query.panel == "changes":
        return _changes(data, cost, today)
    if query.panel == "email_summary":
        return _email_summary(data, cost, today, query.budget)
    if query.panel == "budget_status":
        return _budget_status(data, cost, today, query.budget)

    start, end = _date_window(query.range, today)
    if start is not None and not data.empty:
        data = data[(data["_d"] >= start) & (data["_d"] <= end)]

    if query.panel == "by_category":
        return _breakdown(data, cost, "business_category", "category")
    if query.panel == "by_resource_group":
        return _breakdown(data, cost, "resource_group", "resource_group")

    is_current_month = query.range in ("this_month", "mtd")
    granularity = "daily" if is_current_month else query.granularity
    return _trend(data, cost, granularity, query.budget, cumulative=is_current_month)
