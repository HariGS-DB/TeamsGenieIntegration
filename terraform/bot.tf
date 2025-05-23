resource "random_uuid" "widgets_scope_id" {}

resource "random_uuid" "bot_id" {}

data "azuread_client_config" "current" {}

resource "azuread_application" "bot" {
  display_name     = "${var.prefix}-bot-sp"
  identifier_uris  = ["api://botid-${random_uuid.bot_id.result}"]
  sign_in_audience = "AzureADandPersonalMicrosoftAccount"
  owners           = [data.azuread_client_config.current.object_id]
  api {
    requested_access_token_version = "2"
    oauth2_permission_scope {
      admin_consent_description  = "Teams can access User Profile"
      admin_consent_display_name = "Teams can access User Profile"
      enabled                    = true
      id                         = random_uuid.widgets_scope_id.result
      type                       = "User"
      user_consent_description   = "Teams can access User Profile and make request on behalf of the User"
      user_consent_display_name  = "Teams can access User Profile"
      value                      = "scope_as_user"
    }
  }
  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph
    resource_access {
      id   = "64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0" # email
      type = "Scope"
    }
    resource_access {
      id   = "7427e0e9-2fba-42fe-b0c0-848c9e6a8182" # offline_access
      type = "Scope"
    }
    resource_access {
      id   = "37f7f235-527c-4136-accd-4a02d197296e" # openid
      type = "Scope"
    }
    resource_access {
      id   = "14dad69e-099b-42c9-810b-d002981feec1" # profile
      type = "Scope"
    }
    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d" # User.Read
      type = "Scope"
    }
  }
  required_resource_access {
    resource_app_id = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d" # Databricks
    resource_access {
      id   = "739272be-e143-11e8-9f32-f2801f1b9fd1" # user_impersonation
      type = "Scope"
    }
  }

  web {
    redirect_uris = ["https://token.botframework.com/.auth/web/redirect"]
  }
}

locals {
  identifier_uri = tolist(azuread_application.bot.identifier_uris)[0]
}

resource "azuread_application_pre_authorized" "example" {
  for_each = toset([
    "5e3ce6c0-2b1f-4285-8d4b-75ee78787346", # Teams web
    "1fec8e78-bce4-4aaf-ab1b-5451cc387264"  # Teams desktop/mobile
  ])
  application_id       = azuread_application.bot.id
  authorized_client_id = each.value

  permission_ids = [for permission in azuread_application.bot.oauth2_permission_scope_ids : permission]
}

resource "azurerm_bot_service_azure_bot" "genie_bot" {
  endpoint            = "https://${azurerm_linux_web_app.genie_app.default_hostname}/api/messages"
  location            = "global"
  microsoft_app_id    = azuread_application.bot.client_id
  microsoft_app_type  = "MultiTenant"
  name                = "${var.prefix}-bot"
  resource_group_name = azurerm_resource_group.genie_rg.name
  sku                 = "F0"
}

resource "azurerm_bot_connection" "bot_aad" {
  name                  = "TeamsAuth2"
  bot_name              = azurerm_bot_service_azure_bot.genie_bot.name
  location              = azurerm_bot_service_azure_bot.genie_bot.location
  resource_group_name   = azurerm_resource_group.genie_rg.name
  service_provider_name = "Aadv2"
  client_id             = azuread_application.bot.client_id
  client_secret         = azuread_application_password.bot.value
  parameters = {
    "tenantId"         = var.tenant_id
    "tokenExchangeUrl" = local.identifier_uri
  }
  scopes = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default" # Databricks
}

resource "azurerm_bot_channel_ms_teams" "teams" {
  bot_name            = azurerm_bot_service_azure_bot.genie_bot.name
  location            = azurerm_bot_service_azure_bot.genie_bot.location
  resource_group_name = azurerm_resource_group.genie_rg.name
}

resource "local_file" "manifest" {
  content = templatefile("${path.module}/manifest.json.tftpl", {
    bot_id = azurerm_bot_service_azure_bot.genie_bot.microsoft_app_id
    api_id = local.identifier_uri
  })
  filename = "${path.module}/../appManifest/manifest.json"
}

resource "azuread_application_password" "bot" {
  application_id = azuread_application.bot.id
}

output "client_secret" {
  sensitive = true
  value     = azuread_application_password.bot.value
}
