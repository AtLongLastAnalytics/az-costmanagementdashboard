###############################################################################
# Base platform resources (US-1.4).
#   T-1.13  storage account (raw + curated)
#   T-1.14  Key Vault
#   T-1.15  user-assigned managed identity + least-privilege RBAC
#
# Network isolation, customer-managed keys, and private endpoints are out of
# scope for this phase; the related checkov checks are skipped with reasons.
###############################################################################

data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

resource "random_string" "kv_suffix" {
  length  = 4
  upper   = false
  special = false
}

# --- T-1.13: data lake storage (raw + curated) -------------------------------
resource "azurerm_storage_account" "data" {
  #checkov:skip=CKV_AZURE_35:Default network Allow — Functions need access; network isolation is out of scope this phase.
  #checkov:skip=CKV_AZURE_59:Public network access is required for the hosted deploy agent and Functions; private networking is out of scope this phase.
  #checkov:skip=CKV2_AZURE_41:App access is via managed identity (no SAS); a SAS expiration policy is not applicable.
  #checkov:skip=CKV_AZURE_33:Queue service is not used by this platform.
  #checkov:skip=CKV_AZURE_206:LRS is sufficient and cheaper; geo-redundancy not required for restate-able cost data.
  #checkov:skip=CKV_AZURE_244:Shared key retained so Terraform can manage containers; the app uses managed identity.
  #checkov:skip=CKV2_AZURE_1:Platform-managed encryption keys; customer-managed keys are out of scope.
  #checkov:skip=CKV2_AZURE_18:CMK out of scope (see above).
  #checkov:skip=CKV2_AZURE_33:Private endpoints are out of scope this phase.
  #checkov:skip=CKV2_AZURE_40:Shared key retained for Terraform container management; app access is via managed identity.
  name                = "st${var.name_prefix}${var.environment}data"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  account_tier                      = "Standard"
  account_replication_type          = "LRS"
  account_kind                      = "StorageV2"
  is_hns_enabled                    = true
  min_tls_version                   = "TLS1_2"
  https_traffic_only_enabled        = true
  allow_nested_items_to_be_public   = false
  public_network_access_enabled     = true
  infrastructure_encryption_enabled = true

  blob_properties {
    # Blob versioning is unavailable with hierarchical namespace (ADLS Gen2);
    # soft-delete provides recovery and `raw` remains the durable source.
    delete_retention_policy {
      days = 7
    }

    container_delete_retention_policy {
      days = 7
    }
  }

  sas_policy {
    expiration_period = "07.00:00:00"
  }

  tags = local.common_tags
}

resource "azurerm_storage_container" "raw" {
  #checkov:skip=CKV2_AZURE_21:Blob read-request logging (diagnostic settings to Log Analytics) is out of scope this phase.
  name                  = "raw"
  storage_account_id    = azurerm_storage_account.data.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "curated" {
  #checkov:skip=CKV2_AZURE_21:Blob read-request logging (diagnostic settings to Log Analytics) is out of scope this phase.
  name                  = "curated"
  storage_account_id    = azurerm_storage_account.data.id
  container_access_type = "private"
}

# --- T-1.14: Key Vault (single runtime secret, RBAC-authorised) ---------------
resource "azurerm_key_vault" "main" {
  #checkov:skip=CKV_AZURE_109:Default network Allow — Functions need access; network isolation out of scope this phase.
  #checkov:skip=CKV_AZURE_189:Public access retained this phase; private endpoints out of scope.
  #checkov:skip=CKV2_AZURE_32:Private endpoint out of scope this phase.
  name                = "kv-${var.name_prefix}-${var.environment}-${random_string.kv_suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 7
  public_network_access_enabled = true

  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }

  tags = local.common_tags
}

# --- T-1.15: user-assigned identity + least-privilege RBAC --------------------
resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${local.prefix}-app"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.common_tags
}

resource "azurerm_role_assignment" "app_blob" {
  scope                = azurerm_storage_account.data.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "app_kv_secrets" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# The deploy identity writes the ACS secrets into Key Vault (RBAC data plane).
resource "azurerm_role_assignment" "deployer_kv_secrets" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}
