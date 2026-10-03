terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Grannus"
      ManagedBy   = "Terraform"
      Region      = "India-Mumbai"
      Compliance  = "DPDP-Act-2023"
    }
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# CloudWatch Log Group for Structured Logs
resource "aws_cloudwatch_log_group" "backend_logs" {
  name              = "/ecs/${var.app_name}-${var.environment}-backend"
  retention_in_days = 90
}

# Security Group for Backend Service
resource "aws_security_group" "backend_sg" {
  name        = "${var.app_name}-${var.environment}-backend-sg"
  description = "Security group for Grannus backend containers"

  ingress {
    description = "Allow inbound HTTP from Load Balancer"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    description = "Outbound to external APIs (Sarvam, Gemini, Supabase)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
