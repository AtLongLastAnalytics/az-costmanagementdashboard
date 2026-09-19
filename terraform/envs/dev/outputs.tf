output "resource_group_name" {
  description = "The platform resource group for this environment."
  value       = azurerm_resource_group.main.name
}

output "data_storage_account_name" {
  description = "Storage account holding the raw and curated containers."
  value       = azurerm_storage_account.data.name
}

output "key_vault_name" {
  description = "Key Vault for the single runtime secret."
  value       = azurerm_key_vault.main.name
}

output "app_identity_client_id" {
  description = "Client ID of the app's user-assigned managed identity."
  value       = azurerm_user_assigned_identity.app.client_id
}

output "cost_export_name" {
  description = "Name of the daily Cost Management export."
  value       = module.cost_exports.export_name
}

output "function_app_name" {
  description = "Name of the transform Function App."
  value       = module.data_pipeline.function_app_name
}

output "workbook_id" {
  description = "Resource ID of the cost visibility Workbook."
  value       = module.reporting.workbook_id
}
