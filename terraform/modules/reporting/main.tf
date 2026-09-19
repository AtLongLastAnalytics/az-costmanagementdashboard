###############################################################################
# Module: reporting
#
# The Azure Workbook dashboard. Each panel is a custom-endpoint query against
# the read-API (panel=kpis|trend|by_category|by_resource_group|changes), with
# the filters wired to workbook parameters.
###############################################################################

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

resource "random_uuid" "workbook" {}

locals {
  api = var.read_api_base_url

  # Reusable custom-endpoint query builder (returns the stringified JSON the
  # workbook expects in a query item's `query` field).
  workbook = {
    version   = "Notebook/1.0"
    "$schema" = "https://github.com/Microsoft/Application-Insights-Workbooks/blob/master/schema/workbook.json"
    items = [
      {
        type    = 1
        content = { json = "## Azure Cost Visibility\nBusiness-readable cloud spend, refreshed daily." }
      },
      {
        type = 9
        content = {
          version = "KqlParameterItem/1.0"
          parameters = [
            {
              id         = "p-range", version = "KqlParameterItem/1.0", name = "Range", type = 2,
              isRequired = true, value = "last_30",
              jsonData = jsonencode([
                { value = "this_month", label = "This month" },
                { value = "last_7", label = "Last 7 days" },
                { value = "last_30", label = "Last 30 days" },
                { value = "last_90", label = "Last 90 days" },
                { value = "all", label = "All" },
              ])
            },
            {
              id         = "p-gran", version = "KqlParameterItem/1.0", name = "Granularity", type = 2,
              isRequired = true, value = "weekly",
              jsonData = jsonencode([
                { value = "daily", label = "Daily" },
                { value = "weekly", label = "Weekly" },
                { value = "monthly", label = "Monthly" },
              ])
            },
            {
              id         = "p-cost", version = "KqlParameterItem/1.0", name = "CostType", type = 2,
              isRequired = true, value = "amortized",
              jsonData = jsonencode([
                { value = "amortized", label = "Amortized" },
                { value = "actual", label = "Actual" },
              ])
            },
            { id = "p-cat", version = "KqlParameterItem/1.0", name = "Category", type = 1, isRequired = false, value = "" },
            { id = "p-rg", version = "KqlParameterItem/1.0", name = "ResourceGroup", type = 1, isRequired = false, value = "" },
            { id = "p-budget", version = "KqlParameterItem/1.0", name = "Budget", type = 1, isRequired = false, value = tostring(var.budget_amount) },
          ]
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query = jsonencode({
            version = "CustomEndpoint/1.0", method = "GET",
            url     = "${local.api}?panel=kpis&cost_type={CostType}&category={Category}&resource_group={ResourceGroup}",
            headers = [],
            transformers = [{ type = "jsonpath", settings = { tablePath = "$", columns = [
              { path = "$.mtd", columnid = "Month to date", columnType = "real" },
              { path = "$.forecast", columnid = "Forecast", columnType = "real" },
              { path = "$.prev_month_to_date", columnid = "Prev month", columnType = "real" },
              { path = "$.change_pct", columnid = "Change %", columnType = "real" },
            ] } }]
          })
          size          = 4
          queryType     = 10
          visualization = "table"
          name          = "kpis"
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query = jsonencode({
            version = "CustomEndpoint/1.0", method = "GET",
            url     = "${local.api}?panel=trend&range={Range}&granularity={Granularity}&cost_type={CostType}&category={Category}&resource_group={ResourceGroup}&budget={Budget}",
            headers = [],
            transformers = [{ type = "jsonpath", settings = { tablePath = "$.series", columns = [
              { path = "$.bucket", columnid = "Bucket", columnType = "datetime" },
              { path = "$.cost", columnid = "Cost", columnType = "real" },
              { path = "$.budget", columnid = "Budget", columnType = "real" },
            ] } }]
          })
          size          = 0
          queryType     = 10
          visualization = "linechart"
          chartSettings = {
            xAxis = "Bucket"
            yAxis = ["Cost", "Budget"]
          }
          name = "trend"
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query = jsonencode({
            version = "CustomEndpoint/1.0", method = "GET",
            url     = "${local.api}?panel=by_category&range={Range}&cost_type={CostType}&resource_group={ResourceGroup}",
            headers = [],
            transformers = [{ type = "jsonpath", settings = { tablePath = "$.items", columns = [
              { path = "$.category", columnid = "Category" },
              { path = "$.cost", columnid = "Cost", columnType = "real" },
            ] } }]
          })
          size          = 0
          queryType     = 10
          visualization = "barchart"
          name          = "by_category"
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query = jsonencode({
            version = "CustomEndpoint/1.0", method = "GET",
            url     = "${local.api}?panel=by_resource_group&range={Range}&cost_type={CostType}&category={Category}",
            headers = [],
            transformers = [{ type = "jsonpath", settings = { tablePath = "$.items", columns = [
              { path = "$.resource_group", columnid = "Resource group" },
              { path = "$.cost", columnid = "Cost", columnType = "real" },
            ] } }]
          })
          size          = 0
          queryType     = 10
          visualization = "barchart"
          name          = "by_resource_group"
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query = jsonencode({
            version = "CustomEndpoint/1.0", method = "GET",
            url     = "${local.api}?panel=changes&cost_type={CostType}&category={Category}&resource_group={ResourceGroup}",
            headers = [],
            transformers = [{ type = "jsonpath", settings = { tablePath = "$.items", columns = [
              { path = "$.category", columnid = "Category" },
              { path = "$.last_week", columnid = "Last week", columnType = "real" },
              { path = "$.this_week", columnid = "This week", columnType = "real" },
              { path = "$.delta_pct", columnid = "Change %", columnType = "real" },
            ] } }]
          })
          size          = 0
          queryType     = 10
          visualization = "table"
          name          = "changes"
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query = jsonencode({
            version = "CustomEndpoint/1.0", method = "GET",
            url     = "${local.api}?panel=budget_status&budget={Budget}&cost_type={CostType}",
            headers = [],
            transformers = [{ type = "jsonpath", settings = { tablePath = "$.items", columns = [
              { path = "$.threshold", columnid = "Threshold" },
              { path = "$.amount", columnid = "Amount", columnType = "real" },
              { path = "$.status", columnid = "Status" },
            ] } }]
          })
          size          = 1
          queryType     = 10
          visualization = "table"
          name          = "budget_status"
        }
      },
    ]
  }
}

resource "azurerm_application_insights_workbook" "dashboard" {
  name                = random_uuid.workbook.result
  resource_group_name = var.resource_group_name
  location            = var.location
  display_name        = "Azure Cost Visibility (${var.prefix})"
  data_json           = jsonencode(local.workbook)
  tags                = var.tags
}
