# Deployment troubleshooting & lessons learned

A record of every real issue hit while standing this platform up, and the fix.
Kept because the *reasoning* is a portfolio asset — it shows the gotchas of a
real Azure serverless + IaC deployment, not just the happy path.

## Authentication

**`az login` failed with MFA / Conditional Access (AADSTS50076).**
The tenant requires MFA. Plain `az login` didn't satisfy it. Fix: log in against
the specific tenant — `az login --tenant <id>`; if the browser redirect hangs,
add `--use-device-code`.

**Terraform provider 403 needing MFA on the Microsoft Graph token.**
`azurerm` v4 fetches a Graph token to resolve claims; that token also needed MFA.
Fix: `az login --tenant <id> --scope "https://graph.microsoft.com/.default" --use-device-code`.

## Terraform / CI gate

**Remote-state RG already existed.**
The bootstrap named state resources per-org, colliding with another deploy. Fix:
name state resources **per-project** (`rg-tfstate-costviz`), isolating them.

**tflint crashed (`sigstore-go` nil-pointer panic).**
tflint >= 0.55 has a plugin-signature verification bug on hosted agents. Fix:
pin `TFLINT_VERSION=v0.54.0` (pre-attestation) and the azurerm ruleset to 0.27.0.

**tflint `terraform_unused_declarations` / `required_version` / standard structure.**
A zero-resource skeleton always leaves something unused. Fixes: create the base
resource group (so `location`/`prefix`/tags are used); add a `terraform {}`
block with `required_version` to every module; give each module the standard
`main.tf`/`variables.tf`/`outputs.tf`.

**checkov findings.**
Storage/KeyVault/Function/plan resources tripped several checks. Fixes: harden
where cheap (TLS1.2, soft-delete, HTTPS-only, `content_type` + `expiration_date`
on secrets) and add documented inline `#checkov:skip=` for controls out of scope
this phase (network isolation, CMK, private endpoints, geo-redundancy). Scoped
the scan to `terraform/envs` + `terraform/modules` (bootstrap excluded).

**`terraform fmt -check` failures.**
Hand-written HCL didn't match the formatter. Fix: run `terraform fmt -recursive`
locally before pushing (the one gate the sandbox can't run).

## Git

**Repo initialised in the wrong directory.**
`git init` was run inside `terraform/bootstrap/`, pushing only that folder (with
its `.tfstate`, a secret leak). Fix: remove the stray `.git`, re-init at the repo
root, and force-push clean over the bad content. Rotated the exposed storage key
as a precaution.

## Azure Functions (Python, Linux Consumption)

The single hardest area. Deploying Python with native deps to Linux Consumption:

1. **`func azure functionapp publish --build remote`** → false "app created before
   Aug 2019, no remote build" bug.
2. **`az functionapp deployment source config-zip`** → "not supported on Linux
   Consumption" (needs run-from-package).
3. **`AzureFunctionApp@2` with identity-based storage** → "unable to find the
   storage account" (the deploy tooling needs a connection string to stage).

**Final working approach:** give the Function App a **connection-string** runtime
storage, **vendor dependencies in CI** (`pip install --target`) and deploy the
self-contained package via `AzureFunctionApp@2`. Business-data access still uses
managed identity — only the runtime storage uses a key.

**`ImportError: GLIBC_2.33 not found` (cryptography/pandas/pyarrow).**
The agent's newer glibc wheels didn't match the runtime. Fix: **pin dependencies**
and force compatible wheels with `pip install --only-binary=:all: --platform
manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 --python-version 3.11
--implementation cp`. (Explicit `--platform` is strict — list both tags so every
package finds a wheel.) Added Application Insights first, which is what surfaced
this error.

## RBAC (data-plane permissions the deploy identity lacked)

Contributor is management-plane only. Several data-plane actions 403'd:

- **Remote state over Entra auth** → deploy identity needs **Storage Blob Data
  Contributor** on the state account.
- **Creating role assignments** (US-1.4/1.5) → needs **User Access Administrator**
  on the RG (Contributor can't write role assignments).
- **Writing Key Vault secrets** (US-5.1) → needs **Key Vault Secrets Officer**.
  Also hit **RBAC propagation delay**: the role assignment and the secret write in
  the same apply raced — the write 403'd. Fix: **re-run the pipeline** once the
  assignment has propagated (a `time_sleep` guard is an option for fresh deploys).

## Cost Management export

**`RP Not Registered: Microsoft.CostManagementExports`.**
Fix: `az provider register --namespace Microsoft.CostManagementExports` (one-time,
per subscription), then re-apply.

**Deprecated `resource_manager_id` on the storage container.**
In azurerm v4 the container's `id` is the resource-manager ID. Fix: use `.id`.

**Export not visible.**
It's subscription-scoped; the portal defaults to the billing-account scope.
Switch the Exports scope to the subscription.

## Read-API / Workbook / alert email

- **Python type checks:** `Query(**dict)` failed strict typing → use
  `Query.model_validate(dict)`; `float(object)` needed a `cast`; secret *name*
  fields tripped bandit S105 → `# noqa: S105`.
- **Workbook renders nothing / needs trust:** custom-endpoint panels need the
  portal added as a trusted origin, and CORS on the function for
  `https://portal.azure.com`.
- **Alert email dumped raw JSON:** added an `email_summary` read-API panel that
  returns ready-made subject/text/html, so the Logic App just passes it through
  and the formatting stays in tested Python.

## Verification approach (given what can't be tested)

- Terraform: `plan` + local gate; workbook/Logic App semantics verified by hand.
- Python: unit tests (transform mapping, read-API panels, report compose);
  coverage-gated at 80%.
- End-to-end: manual smoke tests — trigger the timer functions via the admin
  endpoint, "Run now" the export, run the Logic App trigger, and confirm outputs
  in `curated`, the Workbook, and the inbox.
