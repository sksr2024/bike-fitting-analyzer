import onnxruntime as ort
import cv2
import numpy as np
import boto3
import json
import os
import uuid
from urllib.parse import unquote_plus

s3 = boto3.client("s3")
BUCKET = os.environ.get("S3_BUCKET_IMAGES", "")
MODEL_PATH = "/opt/ml/model/movenet_lightning.onnx"

# ========== MoveNet キーポイント定義 ==========
KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]

SKELETON_CONNECTIONS = [
    (5, 7), (7, 9), (6, 8), (8, 10), (5, 6),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
]

ANGLE_DEFINITIONS = {
    "L_knee":     (11, 13, 15, "Left Knee"),
    "R_knee":     (12, 14, 16, "Right Knee"),
    "L_hip":      (5, 11, 13,  "Left Hip"),
    "R_hip":      (6, 12, 14,  "Right Hip"),
    "L_elbow":    (5, 7, 9,    "Left Elbow"),
    "R_elbow":    (6, 8, 10,   "Right Elbow"),
    "L_shoulder": (7, 5, 11,   "Left Shoulder"),
    "R_shoulder": (8, 6, 12,   "Right Shoulder"),
}

# モデルをグローバルでロード（コールドスタート時に1回だけ）
session = None

def get_session():
    global session
    if session is None:
        session = ort.InferenceSession(MODEL_PATH)
    return session


def calculate_angle(p1, p2, p3):
    v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]])
    v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def run_inference(image_bytes):
    sess = get_session()
    input_name = sess.get_inputs()[0].name
    input_size = sess.get_inputs()[0].shape[1]

    # バイト列から画像をデコード
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image")

    h, w = image.shape[:2]

    # 前処理
    resized = cv2.resize(image, (input_size, input_size))
    input_data = np.expand_dims(resized, axis=0).astype(np.int32)

    # 推論
    outputs = sess.run(None, {input_name: input_data})
    keypoints_raw = outputs[0][0][0]

    keypoints = []
    for kp in keypoints_raw:
        y, x, conf = kp
        keypoints.append((int(x * w), int(y * h), float(conf)))

    return image, keypoints


def draw_results(image, keypoints):
    result = image.copy()
    CONF_THRESHOLD = 0.2

    # 骨格線
    for (i, j) in SKELETON_CONNECTIONS:
        if keypoints[i][2] > CONF_THRESHOLD and keypoints[j][2] > CONF_THRESHOLD:
            pt1 = (keypoints[i][0], keypoints[i][1])
            pt2 = (keypoints[j][0], keypoints[j][1])
            cv2.line(result, pt1, pt2, (0, 255, 128), 3, cv2.LINE_AA)

    # キーポイント
    for x, y, conf in keypoints:
        if conf > CONF_THRESHOLD:
            cv2.circle(result, (x, y), 6, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.circle(result, (x, y), 6, (255, 255, 255), 1, cv2.LINE_AA)

    # 角度算出・描画
    angle_results = {}
    for key, (a, b, c, label) in ANGLE_DEFINITIONS.items():
        if all(keypoints[idx][2] > CONF_THRESHOLD for idx in [a, b, c]):
            p1 = (keypoints[a][0], keypoints[a][1])
            p2 = (keypoints[b][0], keypoints[b][1])
            p3 = (keypoints[c][0], keypoints[c][1])
            angle = calculate_angle(p1, p2, p3)
            angle_results[key] = {"label": label, "angle": round(angle, 1)}

            cv2.putText(result, f"{angle:.1f}", (p2[0] + 10, p2[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(result, f"{angle:.1f}", (p2[0] + 10, p2[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)

            radius = 25
            v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]], dtype=np.float64)
            v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]], dtype=np.float64)
            a1 = np.degrees(np.arctan2(-v1[1], v1[0]))
            a2 = np.degrees(np.arctan2(-v2[1], v2[0]))
            cv2.ellipse(result, p2, (radius, radius), 0, -a1, -a2, (0, 255, 255), 2, cv2.LINE_AA)

    # サマリーパネル
    panel_h = 30 + len(angle_results) * 25 + 10
    overlay = result.copy()
    cv2.rectangle(overlay, (10, 10), (280, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, result, 0.4, 0, result)
    cv2.putText(result, "Bike Fitting Analysis", (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)
    y_pos = 60
    for key, data in angle_results.items():
        cv2.putText(result, f"{data['label']}: {data['angle']} deg", (20, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        y_pos += 25

    return result, angle_results


def lambda_handler(event, context):
    try:
        # S3からの入力キー取得
        input_key = event.get("input_key", "")
        if not input_key:
            return {"statusCode": 400, "body": json.dumps({"error": "input_key is required"})}

        # S3から画像をダウンロード
        response = s3.get_object(Bucket=BUCKET, Key=input_key)
        image_bytes = response["Body"].read()

        # 推論実行
        image, keypoints = run_inference(image_bytes)

        # 結果描画
        result_image, angles = draw_results(image, keypoints)

        # 結果画像をS3にアップロード
        result_key = f"results/{uuid.uuid4()}.png"
        _, buffer = cv2.imencode(".png", result_image)
        s3.put_object(Bucket=BUCKET, Key=result_key, Body=buffer.tobytes(), ContentType="image/png")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "result_key": result_key,
                "angles": angles
            })
        }

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
