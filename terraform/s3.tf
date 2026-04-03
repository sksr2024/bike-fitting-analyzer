# ========================================
# フロントエンド用S3バケット（静的サイトホスティング）
# ========================================
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-frontend-${var.environment}"
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ========================================
# 画像保存用S3バケット
# ========================================
resource "aws_s3_bucket" "images" {
  bucket = "${var.project_name}-images-${var.environment}"
}

resource "aws_s3_bucket_public_access_block" "images" {
  bucket = aws_s3_bucket.images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 画像バケットのライフサイクル（PoCなので30日で自動削除）
resource "aws_s3_bucket_lifecycle_configuration" "images" {
  bucket = aws_s3_bucket.images.id

  rule {
    id     = "auto-delete"
    status = "Enabled"

    filter {}

    expiration {
      days = 30
    }
  }
}

# 画像バケットのCORS設定（ブラウザからPresigned URLでアクセスするため）
resource "aws_s3_bucket_cors_configuration" "images" {
  bucket = aws_s3_bucket.images.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT"]
    allowed_origins = ["*"] # PoCなので全許可。本番ではCloudFrontドメインに限定
    max_age_seconds = 3600
  }
}
