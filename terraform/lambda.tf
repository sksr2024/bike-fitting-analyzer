# ========================================
# 推論Lambda関数
# ========================================
resource "aws_lambda_function" "inference" {
  function_name = "${var.project_name}-inference-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.inference.repository_url}:latest"

  memory_size                    = 1024 # ONNX Runtimeの推論に必要
  timeout                        = 30
  reserved_concurrent_executions = 2

  environment {
    variables = {
      S3_BUCKET_IMAGES = aws_s3_bucket.images.bucket
      ENVIRONMENT      = var.environment
    }
  }
}

# ========================================
# ECRリポジトリ（Lambdaコンテナイメージ用）
# ========================================
resource "aws_ecr_repository" "inference" {
  name                 = "${var.project_name}-inference"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # PoCなので削除時にイメージごと消す

  image_scanning_configuration {
    scan_on_push = false
  }
}

# ========================================
# API処理Lambda関数
# ========================================
resource "aws_lambda_function" "api" {
  function_name    = "${var.project_name}-api-${var.environment}"
  role             = aws_iam_role.lambda_role.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.api_lambda.output_path
  source_code_hash = data.archive_file.api_lambda.output_base64sha256

  memory_size                    = 256
  timeout                        = 30
  reserved_concurrent_executions = 2

  environment {
    variables = {
      S3_BUCKET_IMAGES        = aws_s3_bucket.images.bucket
      INFERENCE_FUNCTION_NAME = aws_lambda_function.inference.function_name
      ENVIRONMENT             = var.environment
    }
  }
}

# API Lambda用のInvoke権限（推論Lambdaを呼び出すため）
resource "aws_iam_role_policy" "lambda_invoke" {
  name = "${var.project_name}-lambda-invoke-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.inference.arn
      }
    ]
  })
}

# API Lambdaのソースコードをzip化
data "archive_file" "api_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/api"
  output_path = "${path.module}/../.build/api_lambda.zip"
}
