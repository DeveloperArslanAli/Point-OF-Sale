# Retail POS Infrastructure
# Terraform configuration for Azure deployment

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
  
  # Remote state configuration (uncomment for production)
  # backend "azurerm" {
  #   resource_group_name  = "tfstate"
  #   storage_account_name = "retailpostfstate"
  #   container_name       = "tfstate"
  #   key                  = "retail-pos.tfstate"
  # }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
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
  description = "Admin email for alerts"
  type        = string
}

variable "enable_aks" {
  description = "Deploy AKS cluster"
  type        = bool
  default     = false
}

variable "enable_container_apps" {
  description = "Deploy Azure Container Apps"
  type        = bool
  default     = true
}

# Locals for resource naming
locals {
  resource_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "terraform"
  }
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "rg-${local.resource_prefix}"
  location = var.location
  tags     = local.common_tags
}

# Random suffix for unique names
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}
