# ---------------------------------------------------------------------------
# State backend bootstrap (remote state — see docs/03-tech-stack.md,
# docs/07-decision-log.md). Run ONCE with LOCAL state.
#   cd terraform/bootstrap
#   terraform init
#   terraform apply
# Then use the `backend_config` output to init the main stack.
# ---------------------------------------------------------------------------

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
  # Intentionally no backend block: bootstrap uses local state.
}

provider "azurerm" {
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
  features {}
}

provider "random" {}

variable "subscription_id" {
  description = "Azure subscription ID. Leave empty to use ARM_SUBSCRIPTION_ID."
  type        = string
  default     = ""
}

variable "project" {
  description = "Short project token for state resource naming (isolates this project's state from other deploys)."
  type        = string
  default     = "costviz"
}

variable "location" {
  description = "Azure region for the state backend. An already-bootstrapped backend is unaffected by this default."
  type        = string
  default     = "eastus"
}

resource "random_string" "suffix" {
  length  = 4
  upper   = false
  special = false
}

locals {
  project_sanitised    = substr(replace(lower(var.project), "/[^a-z0-9]/", ""), 0, 12)
  state_rg_name        = "rg-tfstate-${local.project_sanitised}"
  state_account_name   = substr("sttfstate${local.project_sanitised}${random_string.suffix.result}", 0, 24)
  state_container_name = "tfstate"
}

resource "azurerm_resource_group" "state" {
  name     = local.state_rg_name
  location = var.location
  tags = {
    project      = "azure-cost-visibility"
    purpose      = "terraform-state"
    "managed-by" = "terraform"
  }
}

resource "azurerm_storage_account" "state" {
  name                            = local.state_account_name
  resource_group_name             = azurerm_resource_group.state.name
  location                        = azurerm_resource_group.state.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  # Protect the state: versioning keeps prior state versions; blob + container soft delete give a
  # 30-day recovery window if a state blob or the container is deleted.
  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  tags = azurerm_resource_group.state.tags

  # Guard rail: never let a `terraform destroy` in this bootstrap dir wipe the remote state store.
  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "tfstate" {
  name                  = local.state_container_name
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"

  lifecycle {
    prevent_destroy = true
  }
}

output "backend_config" {
  description = "Values for `terraform init -backend-config=...` on the main stack."
  value = {
    resource_group_name  = azurerm_resource_group.state.name
    storage_account_name = azurerm_storage_account.state.name
    container_name       = azurerm_storage_container.tfstate.name
    key                  = "cost-visibility.tfstate"
  }
}
