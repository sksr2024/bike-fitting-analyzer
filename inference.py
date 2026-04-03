import onnxruntime as ort
import cv2
import numpy as np
import sys
import os

# ========== MoveNet キーポイント定義 ==========
KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]

# 骨格の接続定義（描画用）
SKELETON_CONNECTIONS = [
    (5, 7), (7, 9),      # 左腕: 肩→肘→手首
    (6, 8), (8, 10),     # 右腕: 肩→肘→手首
    (5, 6),              # 肩同士
    (5, 11), (6, 12),    # 肩→腰
    (11, 12),            # 腰同士
    (11, 13), (13, 15),  # 左脚: 腰→膝→足首
    (12, 14), (14, 16),  # 右脚: 腰→膝→足首
]

# バイクフィッティングで重要な角度の定義
# (点A, 頂点, 点B) の順で指定
ANGLE_DEFINITIONS = {
    "L_knee":    (11, 13, 15, "Left Knee"),       # 左膝角: 腰-膝-足首
    "R_knee":    (12, 14, 16, "Right Knee"),       # 右膝角: 腰-膝-足首
    "L_hip":     (5, 11, 13,  "Left Hip"),         # 左股関節角: 肩-腰-膝
    "R_hip":     (6, 12, 14,  "Right Hip"),        # 右股関節角: 肩-腰-膝
    "L_elbow":   (5, 7, 9,    "Left Elbow"),       # 左肘角: 肩-肘-手首
    "R_elbow":   (6, 8, 10,   "Right Elbow"),      # 右肘角: 肩-肘-手首
    "L_shoulder": (7, 5, 11,  "Left Shoulder"),     # 左肩角: 肘-肩-腰
    "R_shoulder": (8, 6, 12,  "Right Shoulder"),    # 右肩角: 肘-肩-腰
}


def calculate_angle(p1, p2, p3):
    """3点から頂点(p2)の角度を算出（度数法）"""
    v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]])
    v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])

    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle = np.degrees(np.arccos(cos_angle))
    return angle


def run_inference(image_path, model_path="models/movenet_lightning.onnx"):
    """MoveNetで推論を実行し、キーポイント座標を返す"""
    # モデルをロード
    session = ort.InferenceSession(model_path)
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape  # [1, 192, 192, 3]

    # 画像を読み込み
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not read image: {image_path}")
        sys.exit(1)

    h, w = image.shape[:2]
    print(f"Input image: {w}x{h}")

    # 前処理: リサイズしてint32に変換
    input_size = input_shape[1]  # 192
    resized = cv2.resize(image, (input_size, input_size))
    input_data = np.expand_dims(resized, axis=0).astype(np.int32)

    # 推論実行
    outputs = session.run(None, {input_name: input_data})
    keypoints = outputs[0][0][0]  # shape: (17, 3) -> y, x, confidence

    # ピクセル座標に変換
    keypoint_pixels = []
    for i, kp in enumerate(keypoints):
        y, x, conf = kp
        px = int(x * w)
        py = int(y * h)
        keypoint_pixels.append((px, py, float(conf)))
        print(f"  {KEYPOINT_NAMES[i]:15s}: ({px:4d}, {py:4d})  conf={conf:.3f}")

    return image, keypoint_pixels


def draw_results(image, keypoints, output_path):
    """骨格・角度・数値を画像に描画して保存"""
    result = image.copy()
    h, w = result.shape[:2]
    CONF_THRESHOLD = 0.2

    # --- 骨格線を描画 ---
    for (i, j) in SKELETON_CONNECTIONS:
        if keypoints[i][2] > CONF_THRESHOLD and keypoints[j][2] > CONF_THRESHOLD:
            pt1 = (keypoints[i][0], keypoints[i][1])
            pt2 = (keypoints[j][0], keypoints[j][1])
            cv2.line(result, pt1, pt2, (0, 255, 128), 3, cv2.LINE_AA)

    # --- キーポイントを描画 ---
    for i, (x, y, conf) in enumerate(keypoints):
        if conf > CONF_THRESHOLD:
            cv2.circle(result, (x, y), 6, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.circle(result, (x, y), 6, (255, 255, 255), 1, cv2.LINE_AA)

    # --- 角度を算出・描画 ---
    print("\n=== Angle Results ===")
    angle_results = {}
    text_y_offset = 30

    for key, (a, b, c, label) in ANGLE_DEFINITIONS.items():
        if all(keypoints[idx][2] > CONF_THRESHOLD for idx in [a, b, c]):
            p1 = (keypoints[a][0], keypoints[a][1])
            p2 = (keypoints[b][0], keypoints[b][1])
            p3 = (keypoints[c][0], keypoints[c][1])

            angle = calculate_angle(p1, p2, p3)
            angle_results[key] = angle
            print(f"  {label:18s}: {angle:6.1f} deg")

            # 角度を頂点の近くに表示
            text_pos = (p2[0] + 10, p2[1] - 10)
            cv2.putText(result, f"{angle:.1f}", text_pos,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(result, f"{angle:.1f}", text_pos,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)

            # 角度の弧を描画
            radius = 25
            v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]], dtype=np.float64)
            v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]], dtype=np.float64)
            angle1 = np.degrees(np.arctan2(-v1[1], v1[0]))
            angle2 = np.degrees(np.arctan2(-v2[1], v2[0]))
            cv2.ellipse(result, p2, (radius, radius),
                        0, -angle1, -angle2, (0, 255, 255), 2, cv2.LINE_AA)
        else:
            print(f"  {label:18s}: LOW CONFIDENCE (skipped)")

    # --- サマリーパネル（左上） ---
    panel_h = 30 + len(angle_results) * 25 + 10
    overlay = result.copy()
    cv2.rectangle(overlay, (10, 10), (280, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, result, 0.4, 0, result)

    cv2.putText(result, "Bike Fitting Analysis", (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)

    y_pos = 60
    for key, angle in angle_results.items():
        label = ANGLE_DEFINITIONS[key][3]
        cv2.putText(result, f"{label}: {angle:.1f} deg", (20, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        y_pos += 25

    # --- 保存 ---
    cv2.imwrite(output_path, result)
    print(f"\nResult saved to: {output_path}")
    return angle_results


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "test_images/sample.png"
    output_path = "test_images/result.png"

    print("=== Bike Fitting Analyzer PoC ===\n")
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}\n")

    # 推論実行
    image, keypoints = run_inference(input_path)

    # 結果描画
    angles = draw_results(image, keypoints, output_path)

    print("\nDone!")
