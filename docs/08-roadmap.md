# Roadmap

A phased build plan. Each phase ends with something demo-able, so the project is never far from a state you can show a client or interviewer.

## Phase 1 — Foundation (engineering rigour first)
- Terraform repo scaffold, modular layout, remote state in Azure Storage with blob-lease locking.
- Azure DevOps pipeline with an OIDC (Workload Identity Federation) service connection.
- Resource group, storage account (`raw` + `curated`), Key Vault, base Managed Identities and RBAC.
- **Demo:** `terraform plan` on a PR and `terraform apply` on merge, deploying empty-but-correct infrastructure with no stored secrets.

## Phase 2 — Data path
- Configure Cost Management Export → `raw` (daily, amortised).
- Build the `transform` function and the service-to-business-category mapping table → `curated` Parquet.
- Add the late/missing-export guard and period-overwrite logic.
- **Demo:** a fresh daily export automatically becomes clean, business-labelled curated data.

## Phase 3 — Dashboard
- Build the `read-api` function (read `curated`, group/delta/bucket, return JSON).
- Build the Azure Workbook with the six filters and all approved panels, fed via the custom endpoint.
- **Demo:** the live dashboard — spend by category, by resource group, by week/month, with the "this month" view.

## Phase 4 — Alerting
- Cost Management Budgets at the chosen thresholds.
- Action Group → Logic App → Office 365 / SendGrid email.
- **Demo:** crossing a threshold fires a real email automatically.

## Phase 5 — Weekly report
- `weekly-report` timer function: week-over-week deltas, top movers, simple trend/forecast, emailed.
- **Demo:** an automated Monday-morning report landing in the inbox.

## Phase 6 — Polish for market
- README, architecture diagram, and a "what this solution itself costs to run" section.
- Optional: Cost Management anomaly detection wired into the same Action Group; a daily pipeline health check.
- **Demo:** the full, marketable package — a self-running platform plus the story of the judgement behind it.

## Why this ordering

Engineering rigour (IaC + CI/CD) goes first so every later phase is deployed the same disciplined way. The data path precedes the dashboard because the dashboard is only as good as the curated data behind it. Alerting and the report come after there is real data to alert and report on. Polish is last because it packages what already works rather than propping up what doesn't.
