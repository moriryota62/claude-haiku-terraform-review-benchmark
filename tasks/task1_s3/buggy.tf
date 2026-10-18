terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "bucket_name" {
  type        = string
  description = "S3 bucket name"
}

variable "tags" { # @seed:S1_VAR_NO_META
  default = {}
}

resource "aws_s3_bucket" "s3_bucket" { # @seed:S1_NAME_REPEAT
  bucket = var.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.s3_bucket.id

  versioning_configuration {
    status = "Suspended" # @seed:S1_VERSIONING_SUSPENDED
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.s3_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "main" {
  bucket = aws_s3_bucket.s3_bucket.id

  block_public_acls       = true
  block_public_policy     = false # @seed:S1_PAB_WEAK
  ignore_public_acls      = true
  restrict_public_buckets = false # @seed:S1_PAB_WEAK
}

data "aws_iam_policy_document" "public_read" {
  statement {
    sid       = "PublicRead"
    effect    = "Allow"
    actions   = ["s3:GetObject"] # @seed:S1_PUBLIC_POLICY
    resources = ["${aws_s3_bucket.s3_bucket.arn}/*"]

    principals { # @seed:S1_PUBLIC_POLICY
      type        = "*" # @seed:S1_PUBLIC_POLICY
      identifiers = ["*"] # @seed:S1_PUBLIC_POLICY
    }
  }
}

resource "aws_s3_bucket_policy" "public_read" {
  bucket = aws_s3_bucket.s3_bucket.id
  policy = data.aws_iam_policy_document.public_read.json

  depends_on = [aws_s3_bucket_public_access_block.main]
}

output "bucket_arn" { # @seed:S1_OUTPUT_NO_DESC
  value = aws_s3_bucket.s3_bucket.arn
}
