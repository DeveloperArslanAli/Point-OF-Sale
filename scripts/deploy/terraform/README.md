# Retail POS Terraform Infrastructure

This directory contains Terraform configurations for deploying the Retail POS system to Azure.

## Prerequisites

1. **Azure CLI** - Authenticated with `az login`
2. **Terraform** - Version 1.5.0 or later
3. **Azure Subscription** - With appropriate permissions

## Quick Start

```bash
# Initialize Terraform
terraform init

# Review the plan
terraform plan -var="admin_email=your@email.com"

# Apply the configuration
terraform apply -var="admin_email=your@email.com"
```

## Environment Configuration

Create a `terraform.tfvars` file for your environment:

```hcl
# Development
environment    = "dev"
location       = "eastus"
project_name   = "retailpos"
admin_email    = "admin@yourcompany.com"

# Container Apps (recommended for most deployments)
enable_container_apps = true
enable_aks            = false

# Optional: Stripe integration
stripe_secret_key     = "sk_test_..."
stripe_webhook_secret = "whsec_..."

# Optional: Sentry error tracking
sentry_dsn = "https://..."
```

## Infrastructure Components

| Component | Resource | Purpose |
|-----------|----------|---------|
| **Compute** | Azure Container Apps | Serverless containers for API and Celery workers |
| **Database** | PostgreSQL Flexible Server | Primary data store |
| **Cache** | Azure Redis Cache | Session store, Celery broker, caching |
| **Registry** | Azure Container Registry | Docker image storage |
| **Monitoring** | Log Analytics + App Insights | Observability |
| **Security** | Azure Key Vault | Secrets management |

## File Structure

```
terraform/
├── main.tf           # Main configuration, providers, resource group
├── database.tf       # PostgreSQL Flexible Server
├── redis.tf          # Azure Cache for Redis
├── container_apps.tf # Container Apps for API and workers
├── monitoring.tf     # Log Analytics, App Insights, alerts
├── keyvault.tf       # Key Vault for secrets
├── variables.tf      # Input variable definitions
├── outputs.tf        # Output values
└── README.md         # This file
```

## Environments

### Development
- Minimal resources (Basic SKUs)
- Single replicas
- 7-day log retention

### Staging
- Medium resources
- 2 replicas minimum
- 30-day log retention

### Production
- Premium resources
- 3+ replicas with auto-scaling
- Zone redundancy
- Geo-redundant backups
- 90-day log retention

## Deployment

### First-Time Setup

```bash
# Initialize Terraform
terraform init

# Create workspace for environment
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod

# Select workspace
terraform workspace select dev

# Apply
terraform apply -var-file="dev.tfvars"
```

### CI/CD Integration

The outputs from Terraform can be used in your CI/CD pipeline:

```bash
# Get outputs for deployment
export ACR_LOGIN_SERVER=$(terraform output -raw acr_login_server)
export API_URL=$(terraform output -raw container_app_api_url)

# Push image to ACR
az acr login --name $ACR_LOGIN_SERVER
docker push $ACR_LOGIN_SERVER/retail-pos-api:latest
```

## Costs

Estimated monthly costs (USD):

| Environment | Estimate |
|-------------|----------|
| Development | ~$80-120 |
| Staging     | ~$150-200 |
| Production  | ~$400-600 |

*Costs vary based on usage and region.*

## Security

- All secrets stored in Key Vault
- TLS encryption for all connections
- Network isolation with service endpoints
- RBAC for resource access
- Audit logging enabled

## Troubleshooting

### Common Issues

1. **Container App not starting**
   - Check container logs: `az containerapp logs show -n <app-name> -g <resource-group>`
   - Verify secrets are configured correctly

2. **Database connection issues**
   - Ensure firewall rules allow Azure services
   - Verify SSL mode is set to `require`

3. **Redis connection issues**
   - Use `rediss://` (with double s) for SSL
   - Check Redis firewall rules
