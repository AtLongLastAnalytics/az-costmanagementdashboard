# Dev notes

Running log of what was built per task, why, and any dependency/version changes.

## US-1.1 — Terraform repo & remote state

**Bootstrap (remote state).** Created `terraform/bootstrap/` — a standalone,
local-state Terraform root that provisions this project's own state backend:
resource group `rg-tfstate-costviz`, storage account `sttfstatecostvizd5ue`
(LRS, TLS1.2, blob versioning, 30-day soft-delete, `prevent_destroy`), and the
`tfstate` container. Named per-project (not per-org) so it stays isolated from
other deploys' state. Applied successfully.

**T-1.1 — repo structure + module skeleton.** Added the `terraform/` layout:
`envs/dev/` root (backend wired to the bootstrap output, providers/versions
pinned to azurerm `~> 4.0`, `cmd-<env>-<resource>` naming) and five documented
module stubs — `cost-exports`, `data-pipeline`, `budgets-alerts`, `notification`,
`reporting`. Module composition is laid out as commented blocks in
`envs/dev/main.tf`, to be uncommented as each epic is implemented. Skeleton
plans to zero resources.

**T-1.5 — lint/security config.** Added `.tflint.hcl` (terraform recommended
preset + azurerm ruleset) and `.checkov.yaml` (scans `terraform/`, fails on
findings). These back the CI gate.

Provider/version changes: introduced `hashicorp/azurerm ~> 4.0` and
`hashicorp/random ~> 3.6` (bootstrap only). No Python dependencies yet.

## US-1.3 — Azure DevOps deployment pipeline

**T-1.9 — pipeline.** Added `azure-pipelines.yml` and the reusable
`.azure/steps-install-terraform.yml` template. Two stages: `Validate`
(fmt-check, tflint, checkov, init/validate/plan) on every run, and `Deploy`
(init + apply) that runs only on `main` and is gated by the
`cost-visibility-dev` ADO Environment. Auth is Workload Identity Federation
(OIDC) via the `azure-cost-visibility-oidc` service connection — no secrets, and
the subscription ID is read at runtime (`az account show`), never hardcoded.
Terraform pinned to 1.9.8 in the pipeline.

**T-1.10 — service connection (manual, ADO portal).** `azure-cost-visibility-oidc`
(Azure Resource Manager -> Workload identity federation). Its identity needs
Contributor on the subscription and Storage Blob Data Contributor on the state
account `sttfstatecostvizd5ue` (so it can read/write remote state via
`use_azuread_auth`).

**T-1.11 — environment gate (manual, ADO portal).** ADO Environment
`cost-visibility-dev` with an approval check; this is the human gate before
apply. For Azure Repos, PR validation is enabled by adding this pipeline as a
Build Validation branch policy on `main`.

**Pipeline restructure.** Reworked `azure-pipelines.yml` to the proven
Plan -> artifact -> gated Apply pattern: the Plan stage publishes `tfplan`, and
the Apply stage applies that exact reviewed plan behind the environment
approval. `serviceConnection` is a compile-time parameter. tflint runs from the
repo root (`--recursive`) so modules are covered; checkov scans only
`terraform/envs` + `terraform/modules` (the bootstrap state store is excluded).

## US-1.4 — base resources (partial)

**T-1.12 — resource group.** Brought forward into `envs/dev/main.tf`: creates
`rg-cmd-dev` with common tags. This also gives the pipeline a real resource to
plan/apply as an end-to-end smoke test.

**T-1.13/1.14/1.15 — base platform (`envs/dev/platform.tf`).** Storage account
`stcmddevdata` (ADLS Gen2, TLS1.2, versioning, 7-day soft-delete, infra
encryption, SAS expiry) with `raw` + `curated` containers; Key Vault
`kv-cmd-dev-<rand>` (RBAC-authorised, purge protection); user-assigned identity
`id-cmd-dev-app` with least-privilege RBAC — Storage Blob Data Contributor on
the data account and Key Vault Secrets User on the vault. Network isolation, CMK,
and private endpoints are deferred (documented checkov skips). Added the
`random` provider (`~> 3.6`) to the dev root.

Note: the deploy identity needs role-assignment rights (User Access
Administrator / RBAC Administrator) on `rg-cmd-dev` for T-1.15's role
assignments — Contributor alone cannot create role assignments.

## US-2.1 — Daily cost export to raw

**T-2.1/2.2 — cost-exports module.** Implemented `modules/cost-exports`: an
`azurerm_subscription_cost_management_export` (Daily, AmortizedCost,
MonthToDate) writing to the `raw` container under `cost-exports/`. Scoped to the
subscription via a `subscription_id` variable (T-2.2); azurerm has no
management-group export resource, so MG/multi-tenant scope is a future extension
(billing-account export, US-6.2). Wired into `envs/dev` with `export_start_date`
/ `export_end_date` variables. Added `data.azurerm_subscription.current`.

**T-2.3 — verification.** Runtime: after apply, trigger the export ("Run now")
and confirm a file lands in `raw/cost-exports/`. The deploy identity may need
Cost Management Contributor at subscription scope if Contributor is insufficient
to create the export.

## US-2.2 — Transform to curated with business categories

First Python work, under `functions/`. Package `cost_transform`:
- `mapping.py` + `mapping.json` (T-2.5) — service→business-category semantic
  layer; case-insensitive, default "Other".
- `transform.py` (T-2.6/2.7/2.8) — reads the latest raw CSV, maps source columns
  onto the canonical curated schema, applies the category mapping, and writes one
  Parquet blob per billing period. Overwrite-by-period gives restatement; a
  watermark blob (last export's last-modified) is the no-new-export guard.
- `storage.py` — `BlobStore` protocol + `AzureBlobStore` (managed identity);
  tests use an in-memory fake.
- `function_app.py` — timer trigger (daily 03:00), calls `run_transform`.
- `tests/` (T-2.9) — hermetic pytest for mapping, transform, restatement, guard,
  and the missing-column error.

CI: added a `python` job to the pipeline (ruff check + format, mypy, pytest with
`--cov-fail-under=80`). New Python deps in `functions/requirements.txt`
(azure-functions, azure-storage-blob, azure-identity, pandas, pyarrow, pydantic,
pydantic-settings).

## Function App hosting + code deploy (data-pipeline module)

Implemented `modules/data-pipeline`: a Linux Consumption Function App (Python
3.11) plus its runtime storage account. Managed identity throughout —
`AzureWebJobsStorage` uses the app's system-assigned identity
(`storage_uses_managed_identity`, granted Blob Data Owner + Queue Data
Contributor on the runtime account); the transform reads/writes the data account
using the user-assigned identity, pinned via `AZURE_CLIENT_ID`. App settings set
`TRANSFORM_STORAGE_ACCOUNT_URL` and enable remote (Oryx) build. `https_only`
on; several function-app/storage checkov checks skipped with reasons.

Deploy: the pipeline's Apply stage publishes the `functions/` code after
`terraform apply`. Iterated on the deploy path (Linux Consumption is finicky):
`func --build remote` hit a known detection bug, and CLI `config-zip` isn't
supported on Linux Consumption. Final approach — vendor dependencies in CI
(`pip install --target=.python_packages/lib/site-packages`) and deploy the
self-contained package via the `AzureFunctionApp@2` task, resolving the app name
from a pipeline variable set off `terraform output`.

Runtime storage decision: the Function App's `AzureWebJobsStorage` uses a
connection string (the standard for Consumption, and required by the deploy
tooling, which couldn't stage a package against identity-based storage). This is
a deliberate, scoped exception — all *business-data* access (raw/curated) still
uses the user-assigned managed identity, never a key. Dropped the system-assigned
identity and the runtime-storage role assignments accordingly.

Deployment lessons (glibc): vendored wheels must match the Functions runtime's
glibc — pinned dependencies and forced `--platform manylinux_2_28_x86_64` +
`manylinux_2_17_x86_64` with `--only-binary=:all:`. Added Application Insights,
which is what surfaced the original `GLIBC_2.33` import error.

## US-3.1 — read-API function

Added `cost_readapi` package (reuses `cost_transform.storage`):
- `params.py` — pydantic `Query` model; validates panel/range/granularity/
  cost_type + the subscription/resource-group/category filters.
- `loader.py` — reads and concatenates curated Parquet blobs.
- `panels.py` — the aggregations: `kpis` (MTD, run-rate forecast, vs last month),
  `trend` (daily/weekly/monthly bucketing, this-month forces daily), `by_category`
  and `by_resource_group` breakdowns, and `changes` (week-over-week deltas).
- `function_app.py` — new HTTP function `costs` (auth level function) returning
  panel JSON; the timer `transform` is unchanged.
- Tests (`test_readapi.py`, `test_loader.py`) cover parsing, each panel, filters,
  and empty data. Coverage + mypy now include `cost_readapi`.

Deploys with the existing pipeline (same `functions/` package).

## US-3.2 — Azure Workbook dashboard

Added `modules/reporting`: an `azurerm_application_insights_workbook` whose
`data_json` is built in HCL via `jsonencode`. Panels are custom-endpoint queries
(`queryType 10`) against the read-API — KPIs, trend (line), by-category and
by-resource-group (bar), and week-over-week changes (table) — with workbook
parameters (Range, Granularity, CostType dropdowns; Category/ResourceGroup text)
substituted into the query URLs. Wired into `envs/dev`, pointed at the function
app's default hostname.

Auth decision: the `costs` endpoint is set to **anonymous** so the workbook's
custom endpoint can call it without embedding a function key (which would be a
secret in the workbook JSON). Deliberate dev-phase tradeoff over low-sensitivity
cost totals; production would front it with APIM / Entra. Added CORS
(`https://portal.azure.com`) on the function app so the portal can call it from
the browser.

## Epic 4 — Budget alerting & notification

Chain: Budget -> Action Group -> Logic App -> ACS Email.

`budgets-alerts` module: `azurerm_consumption_budget_subscription` (configurable
amount; alerts at 50/80/100% actual + 100% forecasted) and an
`azurerm_monitor_action_group` with a Logic App receiver.

`notification` module: Azure Communication Services (communication service +
email service + Azure-managed domain + association), and the Logic App workflow
(HTTP-request trigger fired by the Action Group -> HTTP action to enrich via the
read-API -> HTTP action that POSTs to the ACS `emails:send` REST endpoint). The
ACS endpoint is parsed from the connection string; the sender is the managed
domain's DoNotReply address; the recipient is `var.alert_email`.

Improvement over the plan: the Logic App sends via ACS using its **managed
identity** (Entra auth on the ACS data plane), so the design is **fully
secretless** — no Key Vault connection string needed. Granted the Logic App's
identity Contributor on the ACS resource (least-privilege refinement is a
follow-up).

Highest-risk area of the project (Logic App workflow JSON + ACS send + budget
schema, none unit-testable): verification is `terraform plan` + a manual smoke
test (POST a sample payload to the Logic App trigger and confirm the email).

Human-readable email: added an `email_summary` panel to the read-API that
returns ready-made subject/text/html; the Logic App just passes it through, so
the formatting lives in tested Python rather than the low-code workflow.

Branding: added `cost_readapi/emailfmt.py` — a shared email theme (`wrap_email`
+ `table`) applied by both the alert (`email_summary`) and the weekly report
(`cost_report.compose`). Themed to AtLongLast Analytics (deep navy header,
"Private Data & AI Engineering" tagline, footer linking atlonglastanalytics.com,
brand name corrected to one word). Rendered as a full standalone HTML document
(not a fragment) and stamped with a UTC timestamp so consecutive alerts differ —
this stops Gmail collapsing repeated identical emails behind the "..." toggle.

## US-5.1 — Weekly report function

`cost_report` package: `compose.build_weekly_email` reuses the read-API panels
(`email_summary` + `changes`) to build a subject/text/html digest (unit-tested);
`clients.py` wraps Key Vault + ACS send (I/O, not covered). New timer function
`weekly_report` (Mondays 07:00) reads curated, composes the digest, reads the
ACS connection string + sender from Key Vault via managed identity, and sends
via ACS. New deps: `azure-keyvault-secrets`, `azure-communication-email`.

Wiring: the `notification` module writes the ACS connection string + sender to
Key Vault (`acs-connection-string`, `acs-sender-address`); the function app gets
`REPORT_KEY_VAULT_URI` + `REPORT_RECIPIENT` app settings. The deploy identity was
granted Key Vault Secrets Officer to write the secrets (RBAC data plane); the
app identity already holds Key Vault Secrets User to read them. This realises the
architecture's "single runtime secret in Key Vault."

## Security hardening (Epic 6)

**Least-privilege ACS role.** The Logic App's identity uses the built-in
**"Communication and Email Service Owner"** role, scoped to the single ACS
resource — purpose-built for ACS email and much tighter than Contributor. (A
custom `data_actions` role isn't possible: ACS publishes no data-plane RBAC
operations, which fails with `InvalidDataActionOrNotDataAction`.)

**Optional Entra auth on the read-API.** Added `auth_settings_v2` to the function
app as a **variable-gated, off-by-default** capability (`enable_api_auth`,
`api_auth_client_id`). Left off so the anonymous Workbook queries keep working for
the demo. To turn on for production: create an Entra app registration, set the two
variables, and re-wire the Workbook custom endpoints to send an Entra token for
that audience (the Workbook auth is the fiddly part). APIM was considered and
rejected as heavy/expensive for a cost-optimisation tool; Entra Easy Auth is the
lighter Azure-native path.

## Workbook budget panels (Epic 6 polish)

Closes the two deferred dashboard tasks (T-3.11, T-3.14). Read-API: added a
`budget` query param that puts a flat budget series on `trend`, and a new
`budget_status` panel comparing MTD spend to the 50/80/100% thresholds
(OK/Breached), both unit-tested. Workbook: a `Budget` parameter (default
`var.budget_amount`), a budget line on the trend chart, and a budget-status
table. `budget_amount` now flows into the `reporting` module.

## From-scratch deploy hardening — computed schedule dates

Fixed a reproducibility trap found during a fresh from-scratch deploy: the
budget and cost-export start dates were hard-coded (`budget_start_date`
2026-07-01, `export_start_date` 2026-07-17) and went stale, so Azure rejected
the apply ("Start date for monthly time grain should not be prior to current
month" / export "'from' value cannot be in the past"). Both are now computed at
apply time — the budget module derives the first of the current month
(`formatdate(...timestamp())`) and the export module derives tomorrow
(`timeadd(timestamp(), "24h")`) — with `lifecycle { ignore_changes }` on
`time_period` / `recurrence_period_start_date` so later runs don't drift. The
`budget_start_date` and `export_start_date` variables now default to `""`
(empty = compute); pass an explicit date only to override. Runbook
`docs/00-setup.md` step 6 and the rough-edges table updated accordingly, plus a
note on deleting leftover subscription-scoped budget/export singletons before a
re-deploy. No provider or dependency changes.

## From-scratch deploy hardening — Key Vault deploy grant

The from-scratch test hit a Key Vault chicken-and-egg: Terraform self-grants the
deploy identity `Key Vault Secrets Officer` on the vault (`deployer_kv_secrets`
in `envs/dev/platform.tf`), but when the vault and its ACS secrets already exist
in state and the deploy service principal differs from the run that created them,
`terraform plan` must READ those secrets to refresh before the grant it would
create exists — 403 ForbiddenByRbac. Documented fix: grant the deploy SP
`Key Vault Secrets Officer` at subscription scope as a bootstrap step (runbook
step 5c), which unblocks the plan-time read via RBAC inheritance and, being at a
different scope than Terraform's vault-scoped assignment, doesn't collide with it
on apply. This also removes the previously documented "re-run once for KV
propagation" race. Runbook step 5, step 6, rough-edges table and "not yet
automated" section updated. No Terraform code change.
