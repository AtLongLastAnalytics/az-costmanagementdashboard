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

  # Remote state — created by terraform/bootstrap. Backend blocks can't use
  # variables, so the storage account name (which carries a random suffix) is
  # supplied at init via partial config, keeping it out of version control:
  #   terraform init -backend-config=backend.hcl
  # (or -backend-config="storage_account_name=..."). See backend.hcl.example.
  backend "azurerm" {
    resource_group_name = "rg-tfstate-costviz"
    container_name      = "tfstate"
    key                 = "cost-visibility/dev.tfstate"
    use_azuread_auth    = true
  }
}
