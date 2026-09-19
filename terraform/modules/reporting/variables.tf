variable "prefix" {
  description = "Resource name prefix, e.g. cmd-dev."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to deploy into."
  type        = string
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
}

variable "read_api_base_url" {
  description = "Base URL of the read-API costs endpoint (e.g. https://<app>.azurewebsites.net/api/costs)."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget amount, shown as the budget line and status thresholds."
  type        = number
}
