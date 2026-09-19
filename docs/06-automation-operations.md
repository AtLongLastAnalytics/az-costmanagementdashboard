# Automation & operations

The design goal is that nothing is ever run by hand. This document lists every moving part and what triggers it, so the "zero manual operations" claim can be verified rather than asserted.

## The three operational loops

### Loop 1 — Data refresh (schedule-driven)
- **Cost Management Export** is a native scheduled Azure resource. Configured once in Terraform to run daily; Azure writes the file to `raw` with no code of ours running.
- **`transform` Function** is timer-triggered to run shortly after the export. It reads the new file, applies the category mapping, and overwrites the affected period in `curated`.
- **Self-protection:** the function checks for a new file since its last run and exits early if none — a late or missing export never corrupts `curated`.

### Loop 2 — Dashboard (request-driven)
- The **Workbook** calls the **`read-api` Function** on load and on filter change. Reads are transparently fast over small Parquet. No scheduled component; it serves on demand.

### Loop 3 — Alerting (event-driven)
- **Budgets** evaluate spend continuously. A tripped threshold fires an **Action Group** → **Logic App** → email. Real-time, no schedule, no polling.

### Plus — Weekly report (schedule-driven)
- **`weekly-report` Function** runs on a cron (e.g. Monday 07:00), reads `curated`, computes deltas/trend, and emails the report.

## Deployment automation

Infrastructure is never applied from a laptop.

- A **branch policy** on `main` requires a pull request.
- The PR triggers an **Azure DevOps pipeline** that runs `terraform plan` / what-if and posts the result as a comment for review.
- On merge, a second stage runs `terraform apply` against the target subscription via a **Workload Identity Federation (OIDC) service connection** — no stored secrets.

The only human action in the entire system is reviewing and merging a pull request.

## Failure modes and guards

| Risk | Guard |
|------|-------|
| Export late or missing | `transform` checks for a new file and exits early; no bad write |
| Cost data restated | Transform overwrites by period, so `curated` always holds latest correct figures |
| Function transient failure | Functions are idempotent — re-running reproduces the same `curated` output from `raw` |
| Secret leakage | Single secret in Key Vault; everything else uses Managed Identity; OIDC for deploy |
| Bad infra change | `terraform plan` on PR surfaces the diff before any apply |
| Cost of the tool itself | Consumption-plan functions + object storage; pay only for what runs |

## Operational ownership summary

Data refresh, transformation, dashboard serving, alerting, and the weekly report are all triggered by Azure schedules or events. Infrastructure changes are triggered by a git merge. There is no routine task that requires a person to log in and do something — which is both the operational design and a core part of the marketing story: *event-driven and schedule-driven, zero manual operations.*

## Suggested enhancements (optional)

- **Anomaly detection:** Cost Management has built-in anomaly detection that can notify through the same Action Group — "your spend is abnormal versus your own baseline" is more useful than a static threshold.
- **Scheduled health check:** a lightweight daily check that the export landed and `transform` ran, alerting only on failure.
