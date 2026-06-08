"""
推論 Lambda のエントリポイント (コンテナイメージ用)

Event:
  {"s3_bucket": "...", "s3_key": "uploads/xxx.jpg"}

Response:
  {"result_key": "results/xxx.jpg", "angles": {"L_knee": 145.2, ...}}
"""

import logging
import os
import uuid
from typing import Any

import boto3
import botocore.exceptions

from inference import draw_results, run_inference

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "movenet_lightning.onnx")
TMP_DIR = "/tmp"


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    s3_bucket: str = event["s3_bucket"]
    s3_key: str = event["s3_key"]

    # --- Download input image from S3 to /tmp ---
    input_path = os.path.join(TMP_DIR, f"input_{uuid.uuid4()}.jpg")
    try:
        s3.download_file(s3_bucket, s3_key, input_path)
        logger.info("Downloaded s3://%s/%s -> %s", s3_bucket, s3_key, input_path)
    except botocore.exceptions.ClientError as exc:
        logger.error("S3 download failed: %s", exc)
        raise RuntimeError(f"Failed to download image: {exc}") from exc

    # --- Run pose estimation ---
    output_path = os.path.join(TMP_DIR, f"result_{uuid.uuid4()}.jpg")
    try:
        image, keypoints = run_inference(input_path, model_path=MODEL_PATH)
        angles = draw_results(image, keypoints, output_path)
    except Exception as exc:
        logger.error("Inference failed: %s", exc)
        raise

    # --- Upload annotated result image to S3 ---
    result_key = f"results/{uuid.uuid4()}.jpg"
    try:
        s3.upload_file(output_path, s3_bucket, result_key, ExtraArgs={"ContentType": "image/jpeg"})
        logger.info("Uploaded result: s3://%s/%s", s3_bucket, result_key)
    except botocore.exceptions.ClientError as exc:
        logger.error("S3 upload failed: %s", exc)
        raise RuntimeError(f"Failed to upload result: {exc}") from exc

    return {
        "result_key": result_key,
        "angles": angles,
    }
