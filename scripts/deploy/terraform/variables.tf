# Terraform Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "retailpos"
}

variable "admin_email" {
  description = "Admin email for alerts and notifications"
  type        = string
}

variable "enable_aks" {
  description = "Deploy Azure Kubernetes Service"
  type        = bool
  default     = false
}

variable "enable_container_apps" {
  description = "Deploy Azure Container Apps"
  type        = bool
  default     = true
}

variable "stripe_secret_key" {
  description = "Stripe API secret key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "stripe_webhook_secret" {
  description = "Stripe webhook signing secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "sentry_dsn" {
  description = "Sentry DSN for error tracking"
  type        = string
  default     = ""
  sensitive   = true
}
