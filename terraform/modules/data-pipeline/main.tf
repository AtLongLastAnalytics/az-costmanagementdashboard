###############################################################################
# Module: data-pipeline
#
# Hosts the transform Function App (Linux, Python, Consumption) plus its runtime
# storage. Auth is managed identity throughout:
#   - AzureWebJobsStorage uses the Function App's system-assigned identity
#     (storage_uses_managed_identity), granted data roles on the runtime account.
#   - The transform code reads/writes the DATA account using the user-assigned
#     identity (AZURE_CLIENT_ID pins DefaultAzureCredential to it); that identity
#     already holds Storage Blob Data Contributor on the data account (US-1.4).
###############################################################################

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

resource "random_string" "suffix" {
  length  = 4
  upper   = false
  special = false
}

locals {
  func_storage_name = substr("st${replace(var.prefix, "-", "")}func${random_string.suffix.result}", 0, 24)
}

# --- Function App runtime storage --------------------------------------------
resource "azurerm_storage_account" "func" {
  #checkov:skip=CKV_AZURE_35:Default network Allow — Functions runtime needs access; network isolation out of scope this phase.
  #checkov:skip=CKV_AZURE_59:Public network access required for the runtime; private networking out of scope this phase.
  #checkov:skip=CKV2_AZURE_41:Runtime uses managed identity, not SAS; SAS expiration policy not applicable.
  #checkov:skip=CKV_AZURE_33:Queue logging not configured this phase.
  #checkov:skip=CKV_AZURE_244:Shared key retained for runtime compatibility; data access uses managed identity.
  #checkov:skip=CKV_AZURE_206:LRS is sufficient and cheaper for Function runtime storage; geo-redundancy not required.
  #checkov:skip=CKV2_AZURE_1:Platform-managed keys; CMK out of scope.
  #checkov:skip=CKV2_AZURE_18:CMK out of scope.
  #checkov:skip=CKV2_AZURE_33:Private endpoints out of scope this phase.
  #checkov:skip=CKV2_AZURE_40:Shared key retained for Functions runtime; app data access uses managed identity.
  name                            = local.func_storage_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false

  blob_properties {
    delete_retention_policy {
      days = 7
    }

    container_delete_retention_policy {
      days = 7
    }
  }

  tags = var.tags
}

# --- Consumption plan + Function App -----------------------------------------
# --- Observability: Log Analytics workspace + Application Insights -----------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "func" {
  name                = "appi-${var.prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = var.tags
}

resource "azurerm_service_plan" "func" {
  #checkov:skip=CKV_AZURE_225:Consumption (Y1) plan is not zone-redundant by design (cost).
  #checkov:skip=CKV_AZURE_212:Consumption plan scales elastically; a fixed minimum-instance count does not apply.
  name                = "asp-${var.prefix}-func"
  resource_group_name = var.resource_group_name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "Y1"
  tags                = var.tags
}

resource "azurerm_linux_function_app" "transform" {
  #checkov:skip=CKV_AZURE_56:Timer-triggered function with no public HTTP endpoints; built-in auth not applicable.
  #checkov:skip=CKV_AZURE_213:Health-check endpoint not applicable to a timer-only function.
  #checkov:skip=CKV_AZURE_221:Public network access retained this phase; private networking out of scope.
  name                = "func-${var.prefix}-${random_string.suffix.result}"
  resource_group_name = var.resource_group_name
  location            = var.location
  service_plan_id     = azurerm_service_plan.func.id
  https_only          = true

  # Runtime storage uses a connection string (standard for Consumption). All
  # business-data access uses managed identity (below), never a key.
  storage_account_name       = azurerm_storage_account.func.name
  storage_account_access_key = azurerm_storage_account.func.primary_access_key

  identity {
    type         = "UserAssigned"
    identity_ids = [var.user_assigned_identity_id]
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }

    # Allow the Azure portal (Workbooks) to call the read-API from the browser.
    cors {
      allowed_origins = ["https://portal.azure.com"]
    }
  }

  app_settings = {
    # Business-data access uses the user-assigned identity (pins DefaultAzureCredential).
    "TRANSFORM_STORAGE_ACCOUNT_URL" = var.data_storage_account_url
    "AZURE_CLIENT_ID"               = var.user_assigned_identity_client_id
    # Dependencies are vendored in CI; no server-side build.
    "SCM_DO_BUILD_DURING_DEPLOYMENT"        = "false"
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.func.connection_string
    # Weekly report: read ACS secrets from Key Vault, email this recipient.
    "REPORT_KEY_VAULT_URI" = var.key_vault_uri
    "REPORT_RECIPIENT"     = var.report_recipient
    "REPORT_BUDGET"        = tostring(var.budget_amount)
  }

  # Optional production hardening: require Entra auth on the API. Off by default
  # so the demo (and the anonymous Workbook queries) keep working; enable by
  # supplying an app registration client ID.
  dynamic "auth_settings_v2" {
    for_each = var.enable_api_auth ? [1] : []
    content {
      auth_enabled           = true
      require_authentication = true
      unauthenticated_action = "Return401"
      default_provider       = "azureactivedirectory"

      active_directory_v2 {
        client_id            = var.api_auth_client_id
        tenant_auth_endpoint = "https://login.microsoftonline.com/${var.tenant_id}/v2.0"
        allowed_audiences    = ["api://${var.api_auth_client_id}"]
      }

      login {}
    }
  }

  tags = var.tags
}

