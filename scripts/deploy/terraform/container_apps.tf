# Azure Container Apps Module

# Container App Environment
resource "azurerm_container_app_environment" "main" {
  count = var.enable_container_apps ? 1 : 0
  
  name                       = "cae-${local.resource_prefix}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  
  tags = local.common_tags
}

# Container Registry
resource "azurerm_container_registry" "main" {
  name                = "acr${replace(local.resource_prefix, "-", "")}${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.environment == "prod" ? "Premium" : "Basic"
  admin_enabled       = true
  
  # Geo-replication for production
  dynamic "georeplications" {
    for_each = var.environment == "prod" ? ["westus"] : []
    content {
      location                = georeplications.value
      zone_redundancy_enabled = true
    }
  }
  
  tags = local.common_tags
}

# API Container App
resource "azurerm_container_app" "api" {
  count = var.enable_container_apps ? 1 : 0
  
  name                         = "ca-${local.resource_prefix}-api"
  container_app_environment_id = azurerm_container_app_environment.main[0].id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  
  template {
    min_replicas = var.environment == "prod" ? 2 : 1
    max_replicas = var.environment == "prod" ? 10 : 3
    
    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/retail-pos-api:latest"
      cpu    = var.environment == "prod" ? 1.0 : 0.5
      memory = var.environment == "prod" ? "2Gi" : "1Gi"
      
      env {
        name  = "ENV"
        value = var.environment
      }
      
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      
      env {
        name        = "JWT_SECRET_KEY"
        secret_name = "jwt-secret"
      }
      
      liveness_probe {
        path      = "/health"
        port      = 8000
        transport = "HTTP"
      }
      
      readiness_probe {
        path      = "/health"
        port      = 8000
        transport = "HTTP"
      }
    }
    
    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = 50
    }
  }
  
  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"
    
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
  
  secret {
    name  = "database-url"
    value = "postgresql+asyncpg://${azurerm_postgresql_flexible_server.main.administrator_login}:${random_password.postgres.result}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.main.name}?sslmode=require"
  }
  
  secret {
    name  = "redis-url"
    value = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}/0"
  }
  
  secret {
    name  = "jwt-secret"
    value = random_password.jwt_secret.result
  }
  
  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }
  
  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }
  
  tags = local.common_tags
}

# Celery Worker Container App
resource "azurerm_container_app" "celery_worker" {
  count = var.enable_container_apps ? 1 : 0
  
  name                         = "ca-${local.resource_prefix}-celery"
  container_app_environment_id = azurerm_container_app_environment.main[0].id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  
  template {
    min_replicas = var.environment == "prod" ? 2 : 1
    max_replicas = var.environment == "prod" ? 8 : 2
    
    container {
      name    = "celery-worker"
      image   = "${azurerm_container_registry.main.login_server}/retail-pos-api:latest"
      cpu     = 0.5
      memory  = "1Gi"
      command = ["celery", "-A", "app.infrastructure.celery.worker:celery_app", "worker", "--loglevel=INFO"]
      
      env {
        name  = "ENV"
        value = var.environment
      }
      
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      
      env {
        name        = "CELERY_BROKER_URL"
        secret_name = "redis-url"
      }
    }
  }
  
  secret {
    name  = "database-url"
    value = "postgresql+asyncpg://${azurerm_postgresql_flexible_server.main.administrator_login}:${random_password.postgres.result}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.main.name}?sslmode=require"
  }
  
  secret {
    name  = "redis-url"
    value = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}/0"
  }
  
  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }
  
  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }
  
  tags = local.common_tags
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

output "api_url" {
  value = var.enable_container_apps ? azurerm_container_app.api[0].ingress[0].fqdn : ""
}

output "container_registry_url" {
  value = azurerm_container_registry.main.login_server
}
