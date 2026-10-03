variable "aws_region" {
  description = "AWS India Region for DPDP Act 2023 Data Residency"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "grannus-ruralcare"
}

variable "backend_cpu" {
  description = "Fargate CPU units for backend"
  type        = number
  default     = 1024
}

variable "backend_memory" {
  description = "Fargate Memory (MB) for backend"
  type        = number
  default     = 2048
}
