###############################################################################
# Module: cost-exports
#
# A daily Cost Management Export of amortised cost data to the `raw` container.
# Native scheduled Azure resource — no compute of ours runs to produce the file.
#
# Scope: subscription (azurerm has no management-group export resource; a
# billing-account export would be the multi-tenant extension — see US-6.2).
###############################################################################

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

locals {
  # Tomorrow, so the export's schedule start is never in the past on a fresh
  # deploy (Azure rejects a 'from' value that is already past).
  export_start = formatdate("YYYY-MM-DD'T'00:00:00'Z'", timeadd(timestamp(), "24h"))
}

resource "azurerm_subscription_cost_management_export" "daily" {
  name                         = var.name
  subscription_id              = var.subscription_id
  recurrence_type              = "Daily"
  recurrence_period_start_date = var.recurrence_start_date != "" ? var.recurrence_start_date : local.export_start
  recurrence_period_end_date   = var.recurrence_end_date

  # start date is fixed at creation; a later plan recomputes local.export_start
  # from timestamp(), so ignore it to avoid perpetual drift.
  lifecycle {
    ignore_changes = [recurrence_period_start_date]
  }

  export_data_storage_location {
    container_id     = var.storage_container_id
    root_folder_path = var.root_folder_path
  }

  export_data_options {
    # Amortised spreads reservation / savings-plan costs correctly rather than
    # showing them as up-front spikes. Month-to-date on a daily cadence gives a
    # fresh cumulative file each day.
    type       = "AmortizedCost"
    time_frame = "MonthToDate"
  }
}
