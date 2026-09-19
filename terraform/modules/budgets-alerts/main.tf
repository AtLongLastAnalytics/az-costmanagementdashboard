###############################################################################
# Module: budgets-alerts
#
# A subscription Cost Management Budget with actual + forecasted thresholds,
# and the Action Group it fires (which invokes the notification Logic App).
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
  # First of the current month, so a fresh deploy in any month is a valid start.
  start_of_month = formatdate("YYYY-MM-01'T'00:00:00'Z'", timestamp())
}

resource "azurerm_monitor_action_group" "budget" {
  name                = "ag-${var.prefix}-budget"
  resource_group_name = var.resource_group_name
  short_name          = "cmdbudget"

  logic_app_receiver {
    name                    = "notify"
    resource_id             = var.logic_app_id
    callback_url            = var.logic_app_callback_url
    use_common_alert_schema = false
  }

  tags = var.tags
}

resource "azurerm_consumption_budget_subscription" "monthly" {
  name            = "budget-${var.prefix}-monthly"
  subscription_id = var.subscription_id
  amount          = var.budget_amount
  time_grain      = "Monthly"

  time_period {
    start_date = var.budget_start_date != "" ? var.budget_start_date : local.start_of_month
  }

  # start_date is fixed at creation; a later plan recomputes local.start_of_month
  # from timestamp(), so ignore it to avoid perpetual drift.
  lifecycle {
    ignore_changes = [time_period]
  }

  notification {
    enabled        = true
    threshold      = 50
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_groups = [azurerm_monitor_action_group.budget.id]
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_groups = [azurerm_monitor_action_group.budget.id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_groups = [azurerm_monitor_action_group.budget.id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_groups = [azurerm_monitor_action_group.budget.id]
  }
}
