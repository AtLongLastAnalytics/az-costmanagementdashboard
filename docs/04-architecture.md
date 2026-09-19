# Architecture

## Guiding principles

Four principles drive every decision in this design:

**One source of truth.** Curated cost data lives in exactly one place (`curated` Parquet). Nothing is duplicated into a second store that could drift or need reconciling.

**Lean by intent.** Every service must earn its place. A tool whose purpose is cutting cost should not be wasteful itself, and should not carry components heavier than its data volume requires.

**Zero manual operations.** Everything that runs is triggered by a schedule or an event. The only human action in the whole system is merging a pull request.

**Correctness for financial data.** Cost data gets restated over time, so the design must support overwriting/reprocessing a period cleanly — which rules out append-only stores as the system of record.

## Components and flows

The system is best understood as three independent loops plus the infrastructure pipeline.

### Loop 1 — Data (schedule-driven)

```
Cost Management Export ──daily──▶ Storage: raw container
                                        │
                          timer (after export) ▼
                                  Function: transform
                          (map services → business categories,
                           normalise, overwrite by period)
                                        │
                                        ▼
                              Storage: curated (Parquet)
                                        │
                              (single source of truth)
```

The export is a native scheduled Azure resource — no code of ours runs to produce the daily file. The `transform` function checks for a new file and exits early if none, so missing/late exports are safe. Reprocessing overwrites the affected period rather than appending, which keeps restated cost data correct.

**Why no Event Grid:** real-time landing isn't needed for a daily/weekly cadence. A timer set to run after the export is simpler and removes a service. Event Grid would solve a latency problem this system doesn't have.

### Loop 2 — Dashboard serving (request-driven)

```
Azure Workbook ──custom endpoint, with filter params──▶ Function: read-api
                                                              │
                                                   reads curated Parquet,
                                              groups / deltas / buckets server-side
                                                              │
                                                              ▼
                                                    shaped JSON ──▶ Workbook renders
```

Workbooks cannot read Parquet, so the `read-api` function is a thin read layer over the source of truth. The six dashboard filters (time range, subscription, resource group, business category, cost type, granularity) are passed as query-string parameters; the function does the aggregation and returns exactly what each panel needs.

**Why this and not Log Analytics:** feeding the Workbook natively would mean copying cost data into a Log Analytics custom table. That was rejected — a logging store is append-only and the wrong home for restate-able financial data, and it would create a second copy to keep in sync. The custom-endpoint route keeps Parquet as the only store. The trade-off accepted is more aggregation logic written in the function instead of in KQL. (Full reasoning in the decision log.)

**Future ceiling:** if a client's data ever grows to millions of rows per day, the principled upgrade is Azure Data Explorer — a real KQL analytics database (not a logging store) the Workbook can query natively. That is a future-client problem, not a current need.

### Loop 3 — Alerting (event-driven)

```
Cost Management Budgets ──threshold tripped──▶ Action Group ──▶ Logic App ──▶ Office 365 / SendGrid email
```

Budgets evaluate spend continuously and fire in real time at the configured thresholds. This loop has no schedule and no polling.

### Plus — the weekly report (schedule-driven)

```
timer (e.g. Mon 07:00) ──▶ Function: weekly-report
                              reads curated, computes WoW deltas,
                              top movers, simple trend/forecast
                              ──▶ email
```

### Infrastructure pipeline (deploy automation)

```
Pull request ──▶ Azure DevOps: terraform plan + what-if (posted to PR)
Merge to main ──▶ Azure DevOps: terraform apply (via OIDC service connection)
```

Infrastructure is never applied from a developer machine. The OIDC (Workload Identity Federation) service connection means no secrets are stored to enable deployment.

## Security model

Each component runs under a **Managed Identity** with least-privilege RBAC — for example the data functions hold Cost Management Reader and scoped Storage roles, nothing more. The single secret (SendGrid key) lives in **Key Vault** and is read at runtime via managed identity. There are no credentials in source, config, or pipeline variables anywhere in the system.

## Multi-tenant framing

Cost Management scopes and the `subscription` dimension in the data model let the same platform serve multiple subscriptions or client tenants under a Management Group. This is what elevates the build from a single-environment demo to a repeatable consulting product — and it costs nothing extra to design in from the start.

## What was deliberately left out

Event Grid, medallion (bronze/silver/gold) layering, Data Factory, Synapse, Log Analytics as a store, and Power BI. Each was considered and excluded because it adds cost or operational surface beyond what this data volume justifies. The discipline of leaving them out is part of the architecture, not an omission from it.
