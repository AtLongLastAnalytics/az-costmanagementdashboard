provider "azurerm" {
  features {}

  # Resolves from this var, else ARM_SUBSCRIPTION_ID, else the az CLI context.
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
}
