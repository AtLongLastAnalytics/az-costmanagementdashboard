output "logic_app_id" {
  description = "Resource ID of the notification Logic App."
  value       = azurerm_logic_app_workflow.notify.id
}

output "logic_app_callback_url" {
  description = "Callback URL of the Logic App HTTP trigger (for the Action Group)."
  value       = azurerm_logic_app_trigger_http_request.budget.callback_url
  sensitive   = true
}
