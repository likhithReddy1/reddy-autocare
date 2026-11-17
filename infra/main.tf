
resource "azurerm_resource_group" "rg" {
  name     = "rg-reddy-autocare"
  location = "eastus2"

  tags = {
    project     = "REDDY AUTOCARE"
    environment = "development"
    managed_by  = "terraform"
  }
}

resource "azurerm_static_web_app" "frontend" {
  name                = "swa-reddy-autocare-likhith-2026"
  resource_group_name = azurerm_resource_group.rg.name
  location            = "eastus2"

  sku_tier = "Free"
  sku_size = "Free"

  tags = {
    project    = "REDDY AUTOCARE"
    managed_by = "terraform"
  }
}
