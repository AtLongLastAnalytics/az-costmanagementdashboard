###############################################################################
# dev environment — root composition.
#
# The base resource group is created here (US-1.4, T-1.12). Feature modules are
# wired in as their epics are built. Naming: <prefix>-<env>-<resource>.
###############################################################################

locals {
  prefix = "${var.name_prefix}-${var.environment}" # cmd-dev

  common_tags = merge(
    {
      project     = "azure-cost-visibility"
      environment = var.environment
      managed_by  = "terraform"
    },
    var.tags,
  )
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.prefix}"
  location = var.location
  tags     = local.common_tags
}

# --- Data pipeline: transform Function App + runtime storage ------------------
module "data_pipeline" {
  source                           = "../../modules/data-pipeline"
  prefix                           = local.prefix
  location                         = var.location
  resource_group_name              = azurerm_resource_group.main.name
  tags                             = local.common_tags
  user_assigned_identity_id        = azurerm_user_assigned_identity.app.id
  user_assigned_identity_client_id = azurerm_user_assigned_identity.app.client_id
  data_storage_account_url         = azurerm_storage_account.data.primary_blob_endpoint
  key_vault_uri                    = azurerm_key_vault.main.vault_uri
  report_recipient                 = var.alert_email
  budget_amount                    = var.budget_amount
  enable_api_auth                  = var.enable_api_auth
  api_auth_client_id               = var.api_auth_client_id
  tenant_id                        = data.azurerm_client_config.current.tenant_id
}
#
module "cost_exports" {
  source                = "../../modules/cost-exports"
  name                  = "${local.prefix}-daily-cost-export"
  subscription_id       = data.azurerm_subscription.current.id
  storage_container_id  = azurerm_storage_container.raw.id
  root_folder_path      = "cost-exports"
  recurrence_start_date = var.export_start_date
  recurrence_end_date   = var.export_end_date
}

module "notification" {
  source              = "../../modules/notification"
  prefix              = local.prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
  read_api_base_url   = "https://${module.data_pipeline.function_app_default_hostname}/api/costs"
  alert_email         = var.alert_email
  budget_amount       = var.budget_amount
  key_vault_id        = azurerm_key_vault.main.id
}

module "budgets_alerts" {
  source                 = "../../modules/budgets-alerts"
  prefix                 = local.prefix
  resource_group_name    = azurerm_resource_group.main.name
  subscription_id        = data.azurerm_subscription.current.id
  budget_amount          = var.budget_amount
  budget_start_date      = var.budget_start_date
  logic_app_id           = module.notification.logic_app_id
  logic_app_callback_url = module.notification.logic_app_callback_url
  tags                   = local.common_tags
}

module "reporting" {
  source              = "../../modules/reporting"
  prefix              = local.prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
  read_api_base_url   = "https://${module.data_pipeline.function_app_default_hostname}/api/costs"
  budget_amount       = var.budget_amount
}
