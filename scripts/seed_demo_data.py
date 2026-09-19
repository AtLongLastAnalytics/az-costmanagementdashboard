"""Seed synthetic curated cost data for documentation screenshots.

Writes ~6 months of realistic, business-categorised cost Parquet into the
`curated` container, matching the schema the read-API expects. Past months
persist (the daily transform only rewrites the current month), so the deployed
Workbook renders a full, realistic dashboard.

The shape is tuned for a small-team footprint: a current month that runs to
about $8k, gentle month-over-month growth, and a modest recent uptick in
Servers spend so the "what changed this week" story has something to show.
Paired with a ~$6,000 budget, the month-to-date lands around 85% used — the
50% and 80% thresholds breached, 100% not yet.

Usage (from the functions/.venv so pandas/pyarrow/azure-storage-blob are present):

    # PowerShell
    $key = az storage account keys list -g rg-cmd-dev -n <data-acct> --query "[0].value" -o tsv
    $env:AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=<data-acct>;AccountKey=$key;EndpointSuffix=core.windows.net"
    python ..\scripts\seed_demo_data.py

To remove it later, delete the blobs under curated/cost/ for the seeded months.
"""

from __future__ import annotations

import calendar
import datetime as dt
import io
import os
import random

import pandas as pd
from azure.storage.blob import BlobServiceClient

random.seed(42)

# Category -> relative weight and a representative raw service. Weights set the
# category mix; they're normalised so the monthly total hits the target below.
CATEGORIES = {
    "Servers": (1.00, "Microsoft.Compute"),
    "Databases": (0.70, "Microsoft.Sql"),
    "Web & Apps": (0.50, "Microsoft.Web"),
    "Storage": (0.40, "Microsoft.Storage"),
    "Networking": (0.25, "Microsoft.Network"),
    "Monitoring": (0.15, "Microsoft.Insights"),
    "Security": (0.10, "Microsoft.KeyVault"),
    "Other": (0.20, "Microsoft.Other"),
}
RESOURCE_GROUPS = ["rg-prod", "rg-data", "rg-dev", "rg-shared"]
SUBSCRIPTION_ID = "00000000-0000-0000-0000-000000000000"
SUBSCRIPTION_NAME = "Demo Subscription"

# --- Tunables ----------------------------------------------------------------
TARGET_CURRENT_MONTH = 8000.0  # a full current month lands near this ($)
MONTHLY_GROWTH = 0.05  # gentle month-over-month growth (older months are smaller)
MONTHS = 6  # how much history to seed
SERVERS_SPIKE_DAYS = 7  # recent Servers uptick window (current month only)
SERVERS_SPIKE_MULT = 1.5  # size of that uptick
# -----------------------------------------------------------------------------

CONTAINER = "curated"
_WEIGHT_SUM = sum(weight for weight, _ in CATEGORIES.values())


def _month_rows(
    year: int,
    month: int,
    last_day: int,
    daily_base: float,
    growth: float,
    spike_from: dt.date | None,
):
    """Build one month of synthetic daily rows.

    Args:
        year: Calendar year.
        month: Calendar month.
        last_day: Last day to generate (the current month stops at today).
        daily_base: Total spend per day across all categories before growth.
        growth: Month's growth factor relative to the current month (<= 1.0).
        spike_from: If set, Servers spend is lifted on/after this date.

    Returns:
        A list of daily per-category cost rows.
    """
    rows = []
    for day in range(1, last_day + 1):
        date = dt.date(year, month, day)
        for category, (weight, service) in CATEGORIES.items():
            resource_group = random.choice(RESOURCE_GROUPS)
            share = weight / _WEIGHT_SUM
            cost = daily_base * growth * share * random.uniform(0.9, 1.1)
            if spike_from and date >= spike_from and category == "Servers":
                cost *= SERVERS_SPIKE_MULT
            cost = round(cost, 2)
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "subscription_id": SUBSCRIPTION_ID,
                    "subscription_name": SUBSCRIPTION_NAME,
                    "resource_group": resource_group,
                    "service_name_raw": service,
                    "business_category": category,
                    "cost_actual": cost,
                    "cost_amortized": cost,
                    "currency": "USD",
                }
            )
    return rows


def _months(today: dt.date, count: int):
    """Return the (year, month) tuples for the last `count` months, oldest first."""
    year, month = today.year, today.month
    out = []
    for _ in range(count):
        out.append((year, month))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    out.reverse()
    return out


def main() -> None:
    """Generate and upload the synthetic curated data."""
    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    service = BlobServiceClient.from_connection_string(conn)
    container = service.get_container_client(CONTAINER)

    today = dt.date.today()
    spike_from = today - dt.timedelta(days=SERVERS_SPIKE_DAYS - 1)
    months = _months(today, MONTHS)

    # Per-day spend for a full current month that totals ~TARGET_CURRENT_MONTH.
    daily_base = TARGET_CURRENT_MONTH / calendar.monthrange(today.year, today.month)[1]

    for index, (year, month) in enumerate(months):
        is_current = (year, month) == (today.year, today.month)
        last_day = today.day if is_current else calendar.monthrange(year, month)[1]
        # Current month = 1.0; each older month is scaled down by the growth rate.
        growth = (1.0 + MONTHLY_GROWTH) ** (index - (MONTHS - 1))
        rows = _month_rows(
            year, month, last_day, daily_base, growth, spike_from if is_current else None
        )
        frame = pd.DataFrame(rows)

        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        name = f"cost/period={year:04d}-{month:02d}/data.parquet"
        container.get_blob_client(name).upload_blob(buffer.getvalue(), overwrite=True)
        total = frame["cost_actual"].sum()
        print(f"uploaded {name} ({len(frame)} rows, ${total:,.0f})")  # noqa: T201

    print("Done. Open the Workbook and select range 'All' or 'Last 90 days'.")  # noqa: T201


if __name__ == "__main__":
    main()
