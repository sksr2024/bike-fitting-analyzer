output "cloudfront_url" {
  description = "CloudFront distribution URL"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "ecr_repository_url" {
  description = "ECR repository URL for inference Lambda"
  value       = aws_ecr_repository.inference.repository_url
}

output "s3_bucket_frontend" {
  description = "Frontend S3 bucket name"
  value       = aws_s3_bucket.frontend.bucket
}

output "s3_bucket_images" {
  description = "Images S3 bucket name"
  value       = aws_s3_bucket.images.bucket
}
