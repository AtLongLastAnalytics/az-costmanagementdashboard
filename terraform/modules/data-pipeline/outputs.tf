output "function_app_name" {
  description = "Name of the transform Function App."
  value       = azurerm_linux_function_app.transform.name
}

output "function_storage_account_name" {
  description = "Name of the Function App runtime storage account."
  value       = azurerm_storage_account.func.name
}

output "function_app_default_hostname" {
  description = "Default hostname of the Function App (for the read-API base URL)."
  value       = azurerm_linux_function_app.transform.default_hostname
}
