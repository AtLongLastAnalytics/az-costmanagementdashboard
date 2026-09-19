# Technical summary

## Overview

The platform is a serverless, event- and schedule-driven system on Azure that ingests cost data, transforms it into a business-friendly model, serves it through an Azure Workbook dashboard, alerts on budget thresholds, and emails an automated weekly comparison report. All infrastructure is defined in Terraform and deployed through Azure DevOps. No part of the running system requires manual intervention.

## End-to-end flow

### 1. Ingestion

A **Cost Management Export** is configured (in Terraform) to run daily. Azure writes amortised cost data as a file into a storage account `raw` container automatically. Nothing on our side runs to make this happen — the export is a native, scheduled Azure resource. Amortised cost is used deliberately so that reservation and savings-plan costs are spread correctly rather than appearing as misleading one-off spikes.

### 2. Transformation

A **timer-triggered Azure Function** (`transform`) runs shortly after the daily export lands. It reads the new file with pandas/pyarrow, applies a service-to-business-category mapping (so `Microsoft.Compute` becomes `Servers`), normalises the schema, and writes curated Parquet to the `curated` container. The function first checks whether a new file exists since its last run and exits early if not, so a late or missing export never causes a bad write.

`curated` Parquet is the single source of truth. Because cost data can be restated (late charges, credits, amortisation), the transform reprocesses and overwrites by period rather than blindly appending — which is only clean to do because the data lives in object storage, not an append-only store.

### 3. Serving the dashboard

The dashboard is an **Azure Workbook**. Workbooks cannot read Parquet directly, so a second **HTTP-triggered Azure Function** acts as a small read API: the Workbook calls it via the custom/ARM endpoint data source, passing the active filter values as query-string parameters. The function reads `curated`, performs the grouping, week-over-week deltas, and daily/weekly bucketing server-side, and returns shaped JSON that the Workbook renders. This keeps Parquet as the only data store — no data is copied into Log Analytics or any other system.

### 4. Alerting

Spend thresholds are implemented with **Cost Management Budgets** (not Azure Monitor metric alerts — cost is not a Monitor metric). Budgets at the chosen thresholds evaluate spend continuously. When one trips, it fires an **Action Group**, which triggers a **Logic App** that sends an email via Office 365 or SendGrid. This path is event-driven and real-time.

### 5. Weekly report

A second timer-triggered Function (`weekly-report`) runs on a cron (e.g. Monday 07:00). It reads `curated`, computes week-over-week deltas, top movers, and a simple trend/forecast, renders the report, and emails it. No manual step is involved.

## Cross-cutting concerns

**Identity and secrets.** Components authenticate with **Managed Identities**; the only secret (e.g. a SendGrid key) lives in **Key Vault**. No credentials are stored in code or pipeline variables. The Azure DevOps service connection uses Workload Identity Federation (OIDC), so deployment also carries no stored secrets.

**Infrastructure as code.** Everything — storage, export, functions, budgets, action group, Logic App, Key Vault, Workbook — is defined in **Terraform** (`azurerm`) with remote state in an Azure Storage account and blob-lease locking.

**CI/CD.** **Azure DevOps Pipelines** (YAML) run `terraform plan` on pull requests and `terraform apply` on merge to `main`, gated by branch policy. Infrastructure is never deployed from a developer's machine.

**Multi-subscription ready.** Cost Management scopes and the data model carry a subscription dimension, so the same platform can serve multiple subscriptions or client tenants under a Management Group — the framing that turns it from a demo into a consulting product.

## Service inventory

Cost Management (Exports + Budgets), Storage account (`raw` + `curated` + Terraform state), Azure Functions (`transform`, `weekly-report`, `read-api`), Logic App + Action Group, Key Vault, Managed Identity, Azure Workbook. No Log Analytics, no Event Grid, no Data Factory or Synapse — each deliberately excluded as more than this data volume needs.
