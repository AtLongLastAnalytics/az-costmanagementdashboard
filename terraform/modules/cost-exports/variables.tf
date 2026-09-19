variable "name" {
  description = "Name of the Cost Management export."
  type        = string
}

variable "subscription_id" {
  description = "Resource ID of the subscription to export costs for (e.g. /subscriptions/<guid>)."
  type        = string
}

variable "storage_container_id" {
  description = "Resource Manager ID of the storage container the export writes to (the raw container)."
  type        = string
}

variable "root_folder_path" {
  description = "Folder within the container under which export files are written."
  type        = string
  default     = "cost-exports"
}

variable "recurrence_start_date" {
  description = "RFC3339 date the daily export schedule begins. Empty = tomorrow (computed), so it is never in the past at creation."
  type        = string
  default     = ""
}

variable "recurrence_end_date" {
  description = "RFC3339 date the daily export schedule ends."
  type        = string
}
