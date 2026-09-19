# terraform/

Infrastructure as code for the Azure Cost Visibility Platform.

## Layout

```
terraform/
  bootstrap/            One-time, local-state root that creates the remote-state
                        backend (rg-tfstate-costviz + storage + tfstate container).
  envs/
    dev/                Dev environment root. Wires the backend and composes modules.
  modules/
    cost-exports/       Daily Cost Management export → raw          (EPIC 2)
    data-pipeline/      Storage (raw/curated) + transform & read-api (EPIC 2/3)
    budgets-alerts/     Cost Management Budgets + Action Group       (EPIC 4)
    notification/       Logic App + Key Vault + email                (EPIC 4)
    reporting/          Workbook dashboard + weekly-report Function  (EPIC 3/5)
```

## Conventions

- Naming: `<prefix>-<env>-<resource>`, e.g. `cmd-dev-rg`. Prefix `cmd` = cost-management-dashboard.
- Providers/versions pinned in each root's `versions.tf`.
- Remote state per environment: container `tfstate`, key `cost-visibility/<env>.tfstate`.
- No secrets, subscription IDs, or tenant IDs in code — variables, Key Vault, and az/pipeline context only.

## Working in an environment

```bash
cd terraform/envs/dev
terraform init      # connects to the remote-state backend
terraform fmt -check
terraform validate
terraform plan
```

Modules are added to `envs/dev/main.tf` as each is implemented; the skeleton
plans to zero resources until then.
