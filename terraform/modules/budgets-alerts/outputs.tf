output "budget_id" {
  description = "Resource ID of the subscription budget."
  value       = azurerm_consumption_budget_subscription.monthly.id
}

output "action_group_id" {
  description = "Resource ID of the budget Action Group."
  value       = azurerm_monitor_action_group.budget.id
}
