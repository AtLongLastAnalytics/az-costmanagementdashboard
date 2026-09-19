variable "prefix" {
  description = "Resource name prefix, e.g. cmd-dev."
  type        = string
}

variable "location" {
  description = "Azure region for the Logic App."
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

variable "data_location" {
  description = "Data residency location for Azure Communication Services."
  type        = string
  default     = "United States"
}

variable "read_api_base_url" {
  description = "Base URL of the read-API costs endpoint (used to enrich the alert)."
  type        = string
}

variable "alert_email" {
  description = "Recipient email address for budget alerts."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget, passed to the read-API so the alert email can show % used."
  type        = number
}

variable "key_vault_id" {
  description = "Key Vault ID to store the ACS connection string + sender address."
  type        = string
}

variable "secret_expiration_date" {
  description = "RFC3339 expiration date for the stored secrets (rotate before this)."
  type        = string
  default     = "2035-01-01T00:00:00Z"
}
