# S3 Bucket for Audio Storage with DPDP 72-Hour Lifecycle Rule

resource "aws_s3_bucket" "audio_storage" {
  bucket = "${var.app_name}-${var.environment}-audio-records"

  tags = {
    Name        = "Grannus Patient Voice Recordings"
    Environment = var.environment
    Compliance  = "DPDP-Act-2023"
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "audio_storage_pab" {
  bucket = aws_s3_bucket.audio_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Default Server-Side Encryption (AES256)
resource "aws_s3_bucket_server_side_encryption_configuration" "audio_storage_sse" {
  bucket = aws_s3_bucket.audio_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Statutory 72-Hour Automated Purge Lifecycle Rule
resource "aws_s3_bucket_lifecycle_configuration" "audio_retention_policy" {
  bucket = aws_s3_bucket.audio_storage.id

  rule {
    id     = "dpdp-72hour-raw-audio-purge"
    status = "Enabled"

    filter {
      prefix = "raw_recordings/"
    }

    expiration {
      days = 3
    }
  }
}
