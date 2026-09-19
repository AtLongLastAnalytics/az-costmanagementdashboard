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

variable "user_assigned_identity_id" {
  description = "Resource ID of the user-assigned managed identity used for data access."
  type        = string
}

variable "user_assigned_identity_client_id" {
  description = "Client ID of the user-assigned identity (pins DefaultAzureCredential)."
  type        = string
}

variable "data_storage_account_url" {
  description = "Blob endpoint of the data storage account (raw/curated), for the transform."
  type        = string
}

variable "key_vault_uri" {
  description = "Key Vault URI the weekly-report function reads ACS secrets from."
  type        = string
}

variable "report_recipient" {
  description = "Recipient email address for the weekly report."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget shown in the weekly report's budget-vs-forecast line."
  type        = number
}

variable "enable_api_auth" {
  description = "Require Entra auth on the read-API function (production hardening). Off for the demo."
  type        = bool
  default     = false
}

variable "api_auth_client_id" {
  description = "Entra app registration client ID used when enable_api_auth is true."
  type        = string
  default     = ""
}

variable "tenant_id" {
  description = "Entra tenant ID, for the API auth endpoint."
  type        = string
  default     = ""
}
