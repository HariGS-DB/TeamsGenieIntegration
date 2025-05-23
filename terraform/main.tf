resource "azurerm_resource_group" "genie_rg" {
  location = var.location
  name     = "${var.prefix}-rg"
}

resource "azurerm_service_plan" "genie_plan" {
  location            = azurerm_resource_group.genie_rg.location
  name                = "${var.prefix}-plan"
  os_type             = "Linux"
  resource_group_name = azurerm_resource_group.genie_rg.name
  sku_name            = "B1"
}

resource "azurerm_linux_web_app" "genie_app" {
  https_only          = true
  location            = azurerm_service_plan.genie_plan.location
  name                = "${var.prefix}-app"
  resource_group_name = azurerm_resource_group.genie_rg.name
  service_plan_id     = azurerm_service_plan.genie_plan.id
  site_config {
    app_command_line = "gunicorn --bind 0.0.0.0 --worker-class aiohttp.worker.GunicornWebWorker --timeout 1200 app:app"
  }
}

resource "local_file" "deploy" {
  content = templatefile("${path.module}/deploy.sh.tftpl", {
    app_name  = azurerm_linux_web_app.genie_app.name
    rg_name   = azurerm_resource_group.genie_rg.name
    plan_name = azurerm_service_plan.genie_plan.name
    location  = azurerm_linux_web_app.genie_app.location
  })
  filename = "${path.module}/../deploy.sh"
}
