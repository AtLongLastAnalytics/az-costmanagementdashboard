output "export_id" {
  description = "Resource ID of the Cost Management export."
  value       = azurerm_subscription_cost_management_export.daily.id
}

output "export_name" {
  description = "Name of the Cost Management export."
  value       = azurerm_subscription_cost_management_export.daily.name
}
