output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "audio_storage_bucket" {
  description = "Name of the S3 audio storage bucket"
  value       = aws_s3_bucket.audio_storage.bucket
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for backend logs"
  value       = aws_cloudwatch_log_group.backend_logs.name
}
