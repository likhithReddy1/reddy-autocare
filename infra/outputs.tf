
output "frontend_url" {
  description = "REDDY AUTOCARE frontend URL"
  value       = "https://${azurerm_static_web_app.frontend.default_host_name}"
}

output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}
