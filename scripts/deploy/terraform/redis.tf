# Redis Cache Module - Azure Cache for Redis

resource "azurerm_redis_cache" "main" {
  name                = "redis-${local.resource_prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  
  capacity            = var.environment == "prod" ? 1 : 0
  family              = var.environment == "prod" ? "P" : "C"
  sku_name            = var.environment == "prod" ? "Premium" : "Basic"
  
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"
  
  redis_configuration {
    maxmemory_policy = "volatile-lru"
  }
  
  # Zone redundancy for production
  dynamic "zones" {
    for_each = var.environment == "prod" ? [1, 2] : []
    content {
      # This is a workaround for dynamic zones
    }
  }
  
  tags = local.common_tags
}

# Redis Firewall Rule - Allow Azure Services
resource "azurerm_redis_firewall_rule" "allow_azure" {
  name                = "AllowAzureServices"
  redis_cache_name    = azurerm_redis_cache.main.name
  resource_group_name = azurerm_resource_group.main.name
  start_ip            = "0.0.0.0"
  end_ip              = "0.0.0.0"
}

output "redis_connection_string" {
  value     = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}/0"
  sensitive = true
}

output "redis_hostname" {
  value = azurerm_redis_cache.main.hostname
}
