# Tech stack

Every technology below was chosen deliberately. Where a more obvious or heavier option exists, the reasoning explains why it was rejected — that reasoning is itself part of the value of the project.

## Data and cost

### Azure Cost Management — Exports
**Used for:** the daily source of cost data.
**Why:** Exports push amortised cost data to storage on a schedule with zero code running on our side. The alternative — polling the Cost Management Query API on a timer — is more fragile, rate-limited, and stateful. Exports give a durable, replayable dataset for free. Amortised cost (rather than actual) is chosen so reservations and savings plans are spread correctly instead of appearing as spikes.

### Azure Cost Management — Budgets
**Used for:** spending threshold alerts.
**Why:** This is the correct primitive for alerting on spend. The original brief described "Azure Monitor alert rules," but cost is not an Azure Monitor metric, so a metric alert cannot watch spend. Budgets evaluate cost continuously and integrate natively with Action Groups. Same outcome the brief intended, implemented correctly.

## Storage

### Azure Storage (ADLS Gen2) — `raw` and `curated` containers
**Used for:** landing raw exports, holding the curated source-of-truth dataset, and Terraform remote state.
**Why:** Object storage is the cheapest durable home for this data and, crucially, supports overwrite-by-period — essential because cost data gets restated. A two-container split (`raw` untouched, `curated` cleaned) gives a clear audit trail and reprocessing path. A medallion (bronze/silver/gold) layout was considered and rejected as overkill for a single small source.

## Compute

### Azure Functions (Consumption plan)
**Used for:** the `transform` job, the `weekly-report` job, and the `read-api` for the dashboard.
**Why:** The workload is small, intermittent, and event/schedule-driven — the textbook case for serverless. Consumption billing means we pay only when functions run, keeping the tool that fights cost from generating much of its own. pandas/pyarrow handle the transforms comfortably at this data size.
**Rejected alternatives:** Azure Data Factory and Synapse — both add cost, services, and operational surface for transformations that are a few lines of pandas. Choosing them here would be over-engineering, the opposite of the project's message.

## Alerting and notification

### Action Groups
**Used for:** connecting a tripped Budget to the notification workflow.
**Why:** Native glue between Budgets and downstream actions (Logic App, function, webhook, email). Standard, well-understood, no custom code.

### Logic Apps
**Used for:** the alert-to-email workflow.
**Why:** Low-code integration with Office 365 / SendGrid connectors, satisfying the brief directly and demonstrating the integration-automation story. (An HTTP-triggered function could do the same job in code; the Logic App is kept to show the low-code path and match the brief. The choice is documented in the decision log.)

### Office 365 / SendGrid
**Used for:** delivering the email itself.
**Why:** Office 365 connector for internal Microsoft-shop delivery; SendGrid as a provider-agnostic alternative for external clients.

## Presentation

### Azure Workbook
**Used for:** the dashboard (spend by service, by resource group, by week/month).
**Why:** Native to the Azure portal, no external BI tool or licence, and it lives where an Azure admin already works. Power BI was considered for a more polished executive view but rejected to avoid an external dependency and licensing — the platform stays entirely inside Azure.
**Note:** Workbooks cannot read Parquet, so the dashboard is fed by the `read-api` function via the custom endpoint data source. Writing cost data into Log Analytics to feed the Workbook natively was explicitly rejected — a logging store is the wrong home for restate-able financial data (see decision log).

## Security

### Managed Identity + Key Vault
**Used for:** service-to-service auth and the single SendGrid secret.
**Why:** No credentials in code, config, or pipeline variables. Least-privilege RBAC (e.g. Cost Management Reader) scopes each identity to only what it needs.

## Infrastructure and delivery

### Terraform (`azurerm` provider)
**Used for:** defining all infrastructure.
**Why:** Reproducible, reviewable, multi-environment, and the dominant IaC tool in enterprise Azure consulting. Remote state in Azure Storage with blob-lease locking. Modular layout (`cost-exports`, `budgets-alerts`, `notification`, `data-pipeline`, `reporting`). Chosen over Bicep for its broader market familiarity and multi-cloud optionality.

### Azure DevOps Pipelines (YAML)
**Used for:** CI/CD.
**Why:** Matches the toolchain most mid-market and enterprise Azure shops actually run, strengthening the consulting story. Uses a Workload Identity Federation (OIDC) service connection, so deployment carries no stored secrets. `terraform plan` on PRs, `terraform apply` on merge — infrastructure is never deployed by hand.
