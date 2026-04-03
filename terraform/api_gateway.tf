# ========================================
# API Gateway (REST API)
# ========================================
resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_name}-api-${var.environment}"
  protocol_type = "HTTP"

  # OPTIONSはプリフライトリクエストというOPTIONSリクエストを自動で送るためのもの
  # max_ageはプリフライトの結果をキャッシュする時間(s)
  cors_configuration {
    allow_headers = ["Content-Type"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_origins = ["*"] # PoCなので全許可
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
}

# POST /analyze エンドポイント
resource "aws_apigatewayv2_integration" "analyze" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "analyze" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /analyze"
  target    = "integrations/${aws_apigatewayv2_integration.analyze.id}"
}

# API GatewayからLambdaを呼び出す権限
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
