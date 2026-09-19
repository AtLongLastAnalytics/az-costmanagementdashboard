###############################################################################
# Module: notification
#
# Azure Communication Services (email) + a Logic App that composes and sends a
# business-readable budget-alert email. The Logic App is triggered by the
# Action Group (US-4.1), enriches the alert by calling the read-API, and sends
# via ACS authenticated with its own managed identity (no secret).
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

# --- Azure Communication Services: email -------------------------------------
resource "azurerm_communication_service" "acs" {
  name                = "acs-${var.prefix}"
  resource_group_name = var.resource_group_name
  data_location       = var.data_location
  tags                = var.tags
}

resource "azurerm_email_communication_service" "email" {
  name                = "acs-email-${var.prefix}"
  resource_group_name = var.resource_group_name
  data_location       = var.data_location
  tags                = var.tags
}

resource "azurerm_email_communication_service_domain" "managed" {
  name              = "AzureManagedDomain"
  email_service_id  = azurerm_email_communication_service.email.id
  domain_management = "AzureManaged"
}

resource "azurerm_communication_service_email_domain_association" "assoc" {
  communication_service_id = azurerm_communication_service.acs.id
  email_service_domain_id  = azurerm_email_communication_service_domain.managed.id
}

# The single runtime secret: ACS connection string in Key Vault, read by the
# weekly-report function via its managed identity. (The alert Logic App uses
# managed identity directly and needs no secret.)
resource "azurerm_key_vault_secret" "acs_connection_string" {
  name            = "acs-connection-string"
  value           = azurerm_communication_service.acs.primary_connection_string
  key_vault_id    = var.key_vault_id
  content_type    = "text/plain"
  expiration_date = var.secret_expiration_date
}

resource "azurerm_key_vault_secret" "acs_sender_address" {
  name            = "acs-sender-address"
  value           = local.sender_address
  key_vault_id    = var.key_vault_id
  content_type    = "text/plain"
  expiration_date = var.secret_expiration_date
}

locals {
  # ACS data-plane endpoint, parsed from the connection string (endpoint is not
  # a secret, so unwrap it for use in the Logic App HTTP action URL).
  acs_endpoint   = nonsensitive(regex("endpoint=(https://[^/;]+)", azurerm_communication_service.acs.primary_connection_string)[0])
  sender_address = "DoNotReply@${azurerm_email_communication_service_domain.managed.from_sender_domain}"
}

# --- Logic App: parse alert -> enrich -> send email --------------------------
resource "azurerm_logic_app_workflow" "notify" {
  name                = "logic-${var.prefix}-notify"
  resource_group_name = var.resource_group_name
  location            = var.location

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_logic_app_trigger_http_request" "budget" {
  name         = "budget-alert"
  logic_app_id = azurerm_logic_app_workflow.notify.id
  schema       = "{}"
}

resource "azurerm_logic_app_action_custom" "enrich" {
  name         = "enrich"
  logic_app_id = azurerm_logic_app_workflow.notify.id
  body = jsonencode({
    type = "Http"
    inputs = {
      method = "GET"
      uri    = "${var.read_api_base_url}?panel=email_summary&range=this_month&budget=${var.budget_amount}"
    }
    runAfter = {}
  })
}

resource "azurerm_logic_app_action_custom" "send_email" {
  name         = "send-email"
  logic_app_id = azurerm_logic_app_workflow.notify.id
  body = jsonencode({
    type = "Http"
    inputs = {
      method = "POST"
      uri    = "${local.acs_endpoint}/emails:send?api-version=2023-03-31"
      headers = {
        "Content-Type" = "application/json"
      }
      authentication = {
        type     = "ManagedServiceIdentity"
        audience = "https://communication.azure.com"
      }
      body = {
        senderAddress = local.sender_address
        recipients    = { to = [{ address = var.alert_email }] }
        content = {
          subject   = "@{body('enrich')?['subject']}"
          plainText = "@{body('enrich')?['text']}"
          html      = "@{body('enrich')?['html']}"
        }
      }
    }
    runAfter = {
      enrich = ["Succeeded"]
    }
  })
  depends_on = [azurerm_logic_app_action_custom.enrich]
}

# The Logic App's identity sends email via ACS (Entra auth, no key). Uses the
# built-in "Communication and Email Service Owner" role — purpose-built for ACS
# email and far tighter than Contributor — scoped to just this ACS resource.
resource "azurerm_role_assignment" "logic_acs" {
  scope                = azurerm_communication_service.acs.id
  role_definition_name = "Communication and Email Service Owner"
  principal_id         = azurerm_logic_app_workflow.notify.identity[0].principal_id
}
