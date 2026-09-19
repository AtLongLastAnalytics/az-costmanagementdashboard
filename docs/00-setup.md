# 00 — Setup: deploy from scratch

The ordered, end-to-end runbook to stand this platform up in a fresh
environment. Follow top to bottom. The "Known rough edges" section at the end
lists the steps most likely to trip you — skim it first.

Reference values used throughout — replace the `<placeholders>` with your own:

| Thing | Value |
|-------|-------|
| Subscription ID | `<subscription-id>` |
| Tenant ID | `<tenant-id>` |
| GitHub environment (approval gate) | `production` |
| State RG / container | `rg-tfstate-costviz` / `tfstate` |
| App RG | `rg-cmd-dev` |

---

## 0. Prerequisites

**Accounts**
- An Azure subscription where you are **Owner** (you'll grant roles and register providers).
- A GitHub account and a repository for this code. (An Azure DevOps alternative is
  documented at the end.)

**Tools (local machine)**
- Azure CLI (`az`)
- Terraform >= 1.6 (`winget install HashiCorp.Terraform`)
- Git (and Git Bash on Windows if you run the shell snippets in this guide)
- Optional: Python 3.11 + a venv, only if you want to run the Python gate locally

---

## 1. Sign in to Azure

The tenant enforces MFA, so log in against it explicitly with device code:

```powershell
az login --tenant <tenant-id> --use-device-code
az account set --subscription <subscription-id>
az account show --output table   # confirm the right subscription is active
```

---

## 2. Register resource providers (one-time per subscription)

The cost export needs its RP registered, or the apply 400s later:

```powershell
az provider register --namespace Microsoft.CostManagementExports --subscription <subscription-id>
# Poll until "Registered":
az provider show --namespace Microsoft.CostManagementExports --query registrationState -o tsv
```

(`Microsoft.Communication`, `Microsoft.Web`, `Microsoft.KeyVault`, `Microsoft.Insights`
usually auto-register on first use; register them the same way if an apply complains.)

---

## 3. Bootstrap the remote state (local, one-time)

Terraform's state lives in a storage account that must exist *before* the main
stack. The bootstrap root uses **local** state to create it.

```powershell
cd terraform\bootstrap
terraform init
terraform apply        # review, type: yes
terraform output backend_config
```

Record the outputs. The storage account name carries a random suffix (e.g.
`sttfstatecostviz<suffix>`). You do **not** edit the backend block —
`terraform/envs/dev/versions.tf` deliberately omits the account name (partial
backend config), so it's supplied at init instead:

- **Pipeline:** resolved automatically — it lists the one account in
  `rg-tfstate-costviz` and passes it to `terraform init`.
- **Local runs:** copy `terraform/envs/dev/backend.hcl.example` to `backend.hcl`
  (git-ignored), set your account name, then `terraform init -backend-config=backend.hcl`.

> The bootstrap's `project` variable (default `costviz`) sets the state RG name
> (`rg-tfstate-costviz`) and account prefix. The workflows and the step 5 grants use
> that name, so **keep the default** — or, if you change `project`, update
> `rg-tfstate-costviz` in `.github/workflows/ci.yml` + `deploy.yml` and the step 5(a)
> scope to match.

---

## 4. GitHub setup

Deployment runs in **GitHub Actions** (`.github/workflows/ci.yml` validates every PR;
`deploy.yml` plans → waits for approval → applies on merge to `main`). Auth to Azure is
**OIDC** — no stored secret. One-time setup:

> You don't create a `terraform.tfvars` or `backend.hcl` for the GitHub deploy — the
> workflow resolves the state account itself and reads `alert_email` from the
> `ALERT_EMAIL` repository variable (below). Those `.example` files are only for running
> Terraform from your own machine.

1. **Repo:** create the GitHub repository and push this code to it.
2. **Create the deploy identity** — an Azure AD app *and* its service principal. A brand-
   new app registration has **no** service principal until you create one, so do both:

   ```powershell
   $appId = az ad app create --display-name "cost-visibility-deploy" --query appId -o tsv
   az ad sp create --id $appId                       # create the service principal
   $spId = az ad sp show --id $appId --query id -o tsv
   "AZURE_CLIENT_ID = $appId"                         # -> repo secret (step 4.4)
   "service principal object id = $spId"              # -> used by the grants in step 5
   ```
   Keep `$appId` and `$spId` for the next steps.
3. **Federated credentials:** on that app, `Certificates & secrets → Federated
   credentials → Add → GitHub Actions`, add three (replace `<org>/<repo>`):
   - Pull request → subject `repo:<org>/<repo>:pull_request`
   - Branch `main` → subject `repo:<org>/<repo>:ref:refs/heads/main`
   - Environment `production` → subject `repo:<org>/<repo>:environment:production`
4. **Repository secrets** (`Settings → Secrets and variables → Actions → Secrets`):
   `AZURE_CLIENT_ID` (the app's client ID), `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
5. **Repository variable** (same page → Variables): `ALERT_EMAIL` = the address that
   receives budget alerts and the weekly report (passed as `TF_VAR_alert_email`, so it
   isn't committed).
6. **Approval gate:** `Settings → Environments → New environment → production`, then add
   yourself under **Required reviewers**. The `apply` job waits on this.
7. **Branch protection:** `Settings → Branches → add rule for main` → require the **CI**
   checks to pass before merging (so `apply` only runs on reviewed, green changes).

---

## 5. Grant the deploy identity its permissions

Your new service principal has **no roles yet**. Grant the four below — Terraform can't
grant itself these. Use **`$spId`** from step 4.2 (if it's not still in your shell,
re-resolve it: `$spId = az ad sp show --id $appId --query id -o tsv`). Use `<state-account>`
from the bootstrap output (step 3).

> Always use the **service principal (Enterprise Application) object ID** — `$spId` — not
> the App Registration's object ID; role assignments reject the latter with
> `PrincipalTypeNotSupported`.

```powershell
$sub = "/subscriptions/<subscription-id>"

# (a) Manage resources across the subscription
az role assignment create --assignee-object-id $spId --assignee-principal-type ServicePrincipal `
  --role "Contributor" --scope $sub

# (b) Read/write remote state over Entra auth (before the pipeline's `terraform init`)
az role assignment create --assignee-object-id $spId --assignee-principal-type ServicePrincipal `
  --role "Storage Blob Data Contributor" `
  --scope "$sub/resourceGroups/rg-tfstate-costviz/providers/Microsoft.Storage/storageAccounts/<state-account>"

# (c) Create the stack's role assignments (app resources live in a new rg)
az role assignment create --assignee-object-id $spId --assignee-principal-type ServicePrincipal `
  --role "User Access Administrator" --scope $sub

# (d) Read/write Key Vault secrets at plan AND apply time. Terraform also grants itself
#     this (vault-scoped) during apply, but plan must READ pre-existing secrets first —
#     a chicken-and-egg. Granting at subscription scope here fixes it and avoids the
#     "KV secret 403 on first apply" propagation race (different scope than Terraform's
#     vault-scoped grant, so no collision).
az role assignment create --assignee-object-id $spId --assignee-principal-type ServicePrincipal `
  --role "Key Vault Secrets Officer" --scope $sub
```

> If the cost export later 403s on create, also grant **Cost Management Contributor**
> at subscription scope to the same identity.

---

## 6. First deployment

Push to `main` (or `Actions → Deploy → Run workflow`). Flow: **plan → approve the
`production` environment → apply → deploy function code.**

Two things to expect on a first, fresh apply:

- **Key Vault secret 403.** If you did the step 5(c) subscription-scope grant, you
  shouldn't see this. Without it, Terraform's own vault-scoped grant hasn't
  propagated when it writes the ACS secrets (or, if the deploy identity changed
  between runs, plan can't even read the existing secrets) — a 403. Fix: do the
  step 5(c) grant and wait a few minutes, then re-run.
- **Schedule dates are computed, not hard-coded.** `budget_start_date` and
  `export_start_date` now default to empty, and the modules fill them at apply time —
  the budget starts on the first of the current month, the export starts tomorrow — so a
  fresh deploy in any month is valid. (`ignore_changes` then pins them so later runs
  don't drift.) Only set the variables explicitly if you need a specific date.

The function code deploy is automatic (deps are vendored in CI and pushed via
`AzureFunctionApp@2`) — no manual publish step.

---

## 7. Verify end to end

**Data pipeline**
```powershell
# Trigger a real export now (or wait for the daily schedule):
#   Portal → Subscriptions → your subscription → Cost management → Exports → Run now
# Then run the transform:
$key = az functionapp keys list -g rg-cmd-dev -n <func-app-name> --query masterKey -o tsv
Invoke-RestMethod -Method Post -Uri "https://<func-app-name>.azurewebsites.net/admin/functions/transform" `
  -Headers @{ "x-functions-key" = $key } -ContentType "application/json" -Body "{}"
# Confirm curated Parquet appeared:
az storage blob list --account-name <data-account> --container-name curated --auth-mode key -o table
```

**Read-API**
```powershell
Invoke-RestMethod "https://<func-app-name>.azurewebsites.net/api/costs?panel=by_category&range=all"
```

**Dashboard** — `Portal → Monitor → Workbooks → Azure Cost Visibility (cmd-dev)`.
If panels error, click through the "add to trusted hosts" prompt once (the custom
endpoints call the function from the portal).

**Alert email** — `Portal → the notify Logic App → Overview → Run Trigger →
budget-alert`; check the inbox and the Logic App run history.

**Weekly report**
```powershell
Invoke-RestMethod -Method Post -Uri "https://<func-app-name>.azurewebsites.net/admin/functions/weekly_report" `
  -Headers @{ "x-functions-key" = $key } -ContentType "application/json" -Body "{}"
```

---

## 8. (Optional) Seed demo data for screenshots

Real spend on a fresh subscription is pennies. To populate the dashboard/emails
with realistic figures:

```powershell
cd functions
$key = az storage account keys list -g rg-cmd-dev -n <data-account> --query "[0].value" -o tsv
$env:AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=<data-account>;AccountKey=$key;EndpointSuffix=core.windows.net"
python ..\scripts\seed_demo_data.py
```

Then open the Workbook with Range = "All", Budget = e.g. 3000.

---

## Known rough edges (read this first)

| Step | Gotcha | Fix |
|------|--------|-----|
| 1 | Plain `az login` fails with MFA (AADSTS50076) | `--tenant … --use-device-code` |
| 3 | Bootstrap suffix vs backend | Not an issue — the backend omits the account name; init supplies it (the workflow auto-resolves it, or local `backend.hcl`) |
| 2 | Export RP not registered → apply 400 | `az provider register` (step 2) |
| 5 | `PrincipalTypeNotSupported` on the role grant | Use the **Enterprise Application** object ID, not the App Registration's |
| 5 | Role-assignment resources 403 | Grant User Access Administrator (step 5a/b) |
| 5/6 | KV secret 403 (write on apply, or read during plan if the deploy identity changed) | Grant the deploy SP **Key Vault Secrets Officer** at subscription scope (step 5c), wait a few min, re-run |
| 6 | Budget/export "already exists" when a prior deploy left them | They're subscription-scoped singletons that survive a state teardown. Delete the leftovers, then re-run: `az consumption budget delete --budget-name budget-cmd-dev-monthly` and `az costmanagement export delete --name cmd-dev-daily-cost-export --scope "/subscriptions/<sub-id>"` |
| 6 | Budget/export start date rejected as past-dated | Now auto-computed (first-of-month / tomorrow); leave the date vars empty |
| 7 | `az storage blob list --auth-mode login` 403 for you | Use `--auth-mode key`, or grant yourself a Storage Blob Data role |

## Not yet automated (candidates to harden reproducibility)

- Exports RP registration (could be an `azurerm_resource_provider_registration`).
- The KV-secret RBAC race is now sidestepped by the step 5(c) subscription-scope
  grant; the in-Terraform vault-scoped self-grant is kept as a fallback for a
  deploy that skips the manual grants.
- The deploy identity's Storage-Blob-Data / User-Access-Administrator grants are
  inherently manual (an identity can't grant itself the permissions it needs before
  it has them) — but they could move into a small `bootstrap`-time script.

---

## Alternative: deploy via Azure DevOps

The primary pipeline is GitHub Actions (above). The repo also ships
`azure-pipelines.yml` — the same plan → approval → apply flow implemented for Azure
DevOps — for teams standardised on ADO. The build steps and the manual RBAC grants
(step 5) are identical; only the CI/CD host and its wiring differ:

1. **Project + repo:** create the ADO project and push this repo to its Git repo (or
   point the pipeline at your GitHub repo via a GitHub service connection).
2. **Service connection:** `Project Settings → Service connections → New → Azure
   Resource Manager → Workload identity federation (automatic)`, scoped to the
   subscription, named **`azure-cost-visibility-oidc`** (matches the YAML's default).
   Its WIF setup grants Contributor automatically, so you can skip the manual
   Contributor grant in step 5.
3. **Environment:** `Pipelines → Environments → New → cost-visibility-dev`, then
   **Approvals and checks → Approvals** → add yourself (the apply gate).
4. **Pipeline:** `Pipelines → New pipeline → your repo → Existing YAML → /azure-pipelines.yml`.
5. **Branch policy:** require a PR on `main` and add the pipeline as **Build validation**.
6. **Pipeline variable:** add `alertEmail` = the recipient address (passed as
   `TF_VAR_alert_email`, so it isn't committed) — the ADO equivalent of the GitHub
   `ALERT_EMAIL` repository variable.

Everything downstream — the bootstrap, RBAC grants, first deploy, and verification —
is the same regardless of which host runs the apply.
</content>
