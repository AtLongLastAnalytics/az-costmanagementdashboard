# Data model

## The single fact table

Everything the dashboard and the weekly report need reduces to one denormalised table of daily cost rows, held as Parquet in the `curated` container. Each row is one service's cost in one resource group, on one day, in one subscription.

| Column | Type | Notes |
|--------|------|-------|
| `date` | date | Day of spend |
| `subscription_id` | string | For multi-subscription / multi-tenant scoping |
| `subscription_name` | string | Human-readable subscription |
| `resource_group` | string | The "which part of the business" cut |
| `service_name_raw` | string | Original Azure service (e.g. `Microsoft.Compute`) |
| `business_category` | string | Translated name (e.g. `Servers`) — baked in by the transform |
| `cost_actual` | decimal | Actual cost |
| `cost_amortized` | decimal | Amortised cost (reservations/savings plans spread) |
| `currency` | string | Billing currency |

Budget thresholds are **not** in this table — they come from the Cost Management Budgets configuration.

## Why the category is baked in upstream

`business_category` is computed by the `transform` function from a service-to-category mapping table, then stored. The dashboard never has to join or translate at query time — the whole point of the translation ("Servers," not "Microsoft.Compute") is realised once, in one place, and every consumer benefits. The mapping table is the project's semantic layer.

## Dashboard requirements driving the model

The approved Workbook layout needs six filters, all driven by columns above (plus Budgets):

1. **Time range** — last 7 / 30 / 90 days, **this month**, MTD, custom. Drives every panel.
2. **Subscription** — multi-select.
3. **Resource group** — multi-select.
4. **Business category** — multi-select, on the translated names.
5. **Cost type** — actual vs amortised (they give different numbers; the user picks).
6. **Granularity** — daily / weekly / monthly. "This month" forces daily resolution.

Every panel is a group-by-and-sum over this one table:

- KPI tiles — sums with date filters (MTD, last month to same day) plus a simple run-rate/linear forecast.
- Spend-over-time trend — sum grouped by day or week, with the budget threshold drawn as a reference line. Axis adapts to the selected range.
- Breakdown bars — sum grouped by `business_category` and by `resource_group`.
- "What changed this week" — this-week sum vs last-week sum per category, with the delta.
- Budget status — current MTD spend vs each configured threshold.

Because `business_category` is pre-computed and the data is small, there are no query-time joins. The `read-api` function performs these aggregations server-side and returns shaped JSON per panel.

## Granularity and the "this month" view

Daily resolution is retained in the curated data (exports land daily), so the dashboard can switch the trend to daily buckets when "this month" is selected — weekly buckets are too coarse for a month-to-date view — and back to weekly for the 90-day view. The `read-api` function handles the bucketing based on the `granularity` parameter.

## Restatement handling

Cost data changes after the fact (late charges, credits, amortisation adjustments). The transform overwrites the affected period in `curated` rather than appending, so the source of truth always reflects the latest correct figures. This is only clean because the data lives in object storage; it is the core reason an append-only store (e.g. Log Analytics) was rejected as the system of record.
