variable "subscription_id" {
  description = "Azure subscription ID. Leave empty to use ARM_SUBSCRIPTION_ID / az CLI context."
  type        = string
  default     = ""
}

variable "environment" {
  description = "Environment name, used in resource naming (cmd-<env>-<resource>)."
  type        = string
  default     = "dev"
}

variable "name_prefix" {
  description = "Resource name prefix. Combined as <prefix>-<environment>-<resource>."
  type        = string
  default     = "cmd" # cost-management-dashboard
}

variable "location" {
  description = "Azure region for platform resources."
  type        = string
  default     = "eastus"
}

variable "tags" {
  description = "Extra tags merged onto every resource."
  type        = map(string)
  default     = {}
}

variable "export_start_date" {
  description = "RFC3339 date the daily cost export schedule begins. Empty = tomorrow (computed), so it is never past at creation."
  type        = string
  default     = ""
}

variable "export_end_date" {
  description = "RFC3339 date the daily cost export schedule ends."
  type        = string
  default     = "2030-01-01T00:00:00Z"
}

variable "alert_email" {
  description = "Recipient email address for budget alerts and the weekly report."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget amount in the billing currency."
  type        = number
  default     = 6000
}

variable "budget_start_date" {
  description = "RFC3339 first-of-month date the budget starts. Empty = first of the current month (computed)."
  type        = string
  default     = ""
}

variable "enable_api_auth" {
  description = "Require Entra auth on the read-API (production). Off for the demo; needs an app registration."
  type        = bool
  default     = false
}

variable "api_auth_client_id" {
  description = "Entra app registration client ID used when enable_api_auth is true."
  type        = string
  default     = ""
}
