"""
POST /analyze
  - Accepts: application/json {"image": "<base64>"} or raw base64 body
  - Saves original image to S3: uploads/{uuid}.jpg
  - Invokes inference Lambda synchronously
  - Returns: {"result_url": "<presigned_url>", "result_key": "...", "angles": {...}}
"""

import base64
import json
import logging
import os
import uuid
from typing import Any

import boto3
import botocore.exceptions

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
lambda_client = boto3.client("lambda")

S3_BUCKET_IMAGES = os.environ["S3_BUCKET_IMAGES"]
INFERENCE_FUNCTION_NAME = os.environ["INFERENCE_FUNCTION_NAME"]

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json",
    }


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": _cors_headers(),
        "body": json.dumps(body),
    }


def _extract_image_bytes(event: dict[str, Any]) -> bytes:
    """Extract raw image bytes from the API Gateway v2 event."""
    headers = event.get("headers") or {}
    content_type = headers.get("content-type", "")
    body = event.get("body", "") or ""
    is_base64 = event.get("isBase64Encoded", False)

    if "application/json" in content_type:
        if is_base64:
            body = base64.b64decode(body).decode("utf-8")
        payload = json.loads(body)
        image_b64 = payload.get("image")
        if not image_b64:
            raise ValueError("Missing 'image' field in JSON body")
        return base64.b64decode(image_b64)

    # Fallback: treat body itself as base64-encoded image bytes
    if is_base64:
        return base64.b64decode(body)

    raise ValueError(
        f"Unsupported Content-Type: {content_type!r}. Use application/json with base64 image."
    )


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    http_ctx = event.get("requestContext", {}).get("http", {})
    logger.info("Request: method=%s path=%s", http_ctx.get("method"), event.get("rawPath"))

    # --- Parse input ---
    try:
        image_bytes = _extract_image_bytes(event)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("Bad request: %s", exc)
        return _response(400, {"error": str(exc)})

    if len(image_bytes) > MAX_IMAGE_BYTES:
        return _response(400, {"error": "Image exceeds 10 MB limit"})

    # --- Upload input image to S3 ---
    input_key = f"uploads/{uuid.uuid4()}.jpg"
    try:
        s3.put_object(
            Bucket=S3_BUCKET_IMAGES,
            Key=input_key,
            Body=image_bytes,
            ContentType="image/jpeg",
        )
        logger.info("Uploaded input image: s3://%s/%s", S3_BUCKET_IMAGES, input_key)
    except botocore.exceptions.ClientError as exc:
        logger.error("S3 upload failed: %s", exc)
        return _response(500, {"error": "Failed to store image"})

    # --- Invoke inference Lambda ---
    inference_payload = json.dumps({
        "s3_bucket": S3_BUCKET_IMAGES,
        "s3_key": input_key,
    })
    try:
        response = lambda_client.invoke(
            FunctionName=INFERENCE_FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=inference_payload.encode(),
        )
    except botocore.exceptions.ClientError as exc:
        logger.error("Lambda invoke failed: %s", exc)
        return _response(500, {"error": "Inference service unavailable"})

    if response.get("FunctionError"):
        error_detail = json.loads(response["Payload"].read())
        logger.error("Inference Lambda error: %s", error_detail)
        return _response(500, {"error": "Inference failed", "detail": error_detail})

    inference_result = json.loads(response["Payload"].read())
    result_key = inference_result.get("result_key")
    angles = inference_result.get("angles", {})

    # --- Generate presigned URL (1 hour) so the browser can fetch the result image ---
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET_IMAGES, "Key": result_key},
        ExpiresIn=3600,
    )

    logger.info("Inference complete. result_key=%s", result_key)
    return _response(200, {
        "result_url": presigned_url,
        "result_key": result_key,
        "angles": angles,
    })
