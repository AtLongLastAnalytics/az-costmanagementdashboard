variable "prefix" {
  description = "Resource name prefix, e.g. cmd-dev."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the Action Group."
  type        = string
}

variable "subscription_id" {
  description = "Subscription resource ID the budget applies to (/subscriptions/<guid>)."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget amount in the billing currency."
  type        = number
}

variable "budget_start_date" {
  description = "RFC3339 first-of-month date the budget starts. Empty = first of the current month (computed)."
  type        = string
  default     = ""
}

variable "logic_app_id" {
  description = "Resource ID of the notification Logic App."
  type        = string
}

variable "logic_app_callback_url" {
  description = "Callback URL of the Logic App HTTP trigger."
  type        = string
}

variable "tags" {
  description = "Tags applied to the Action Group."
  type        = map(string)
}
