import math
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

from inference import calculate_angle, draw_results, run_inference


# ===== calculate_angle tests (pure math, no mocking) =====

def test_right_angle():
    """直交する2ベクトルは90度。"""
    angle = calculate_angle((0.0, 1.0), (0.0, 0.0), (1.0, 0.0))
    assert abs(angle - 90.0) < 0.001


def test_straight_line():
    """3点が一直線上にある場合は180度（+1e-6 ガードによる微小誤差を考慮し 0.1度以内）。"""
    angle = calculate_angle((0.0, 0.0), (1.0, 0.0), (2.0, 0.0))
    assert abs(angle - 180.0) < 0.1


def test_zero_angle():
    """同方向ベクトルは0度（+1e-6 ガードによる微小誤差を考慮し 0.1度以内）。"""
    angle = calculate_angle((0.0, 1.0), (0.0, 0.0), (0.0, 2.0))
    assert abs(angle - 0.0) < 0.1


def test_degenerate_zero_vector():
    """ゼロベクトルが入っても ZeroDivisionError にならない (+1e-6 ガード)。"""
    angle = calculate_angle((0.0, 0.0), (0.0, 0.0), (1.0, 0.0))
    assert isinstance(angle, float)


def test_known_60_degrees():
    """正三角形の内角は60度。"""
    p1 = (0.0, 0.0)
    p2 = (1.0, 0.0)
    p3 = (0.5, math.sqrt(3) / 2)
    angle = calculate_angle(p1, p2, p3)
    assert abs(angle - 60.0) < 0.01


# ===== draw_results tests =====

def test_draw_results_returns_dict(blank_image, dummy_keypoints, tmp_path):
    """draw_results は dict[str, float] を返し、出力ファイルが存在すること。"""
    output = tmp_path / "out.png"
    result = draw_results(blank_image, dummy_keypoints, str(output))
    assert isinstance(result, dict)
    assert output.exists()


def test_draw_results_skips_low_confidence(blank_image, tmp_path):
    """信頼度が閾値(0.2)未満のキーポイントは全てスキップされ、角度が空になる。"""
    low_conf = [(100, 100, 0.1)] * 17
    output = tmp_path / "out.png"
    result = draw_results(blank_image, low_conf, str(output))
    assert result == {}


# ===== run_inference tests =====

def test_run_inference_bad_path_raises(monkeypatch):
    """存在しない画像パスを渡すと ValueError が発生する。"""
    mock_session = MagicMock()
    mock_session.get_inputs.return_value = [
        MagicMock(name="input", shape=[1, 192, 192, 3])
    ]
    monkeypatch.setattr("inference.ort.InferenceSession", lambda path: mock_session)

    with pytest.raises(ValueError, match="Could not read image"):
        run_inference("/nonexistent/path/image.jpg", model_path="fake.onnx")


def test_run_inference_calls_ort(tmp_path, monkeypatch):
    """ort.InferenceSession をモックして run_inference の返り値を検証する。"""
    # 実際に読み込める小さな画像を作成
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img_path = str(tmp_path / "test.jpg")
    cv2.imwrite(img_path, img)

    # 推論出力: shape (1, 1, 17, 3) — y, x, confidence
    mock_output = np.zeros((1, 1, 17, 3), dtype=np.float32)
    mock_session = MagicMock()
    mock_session.get_inputs.return_value = [
        MagicMock(name="input", shape=[1, 192, 192, 3])
    ]
    mock_session.run.return_value = [mock_output]

    monkeypatch.setattr("inference.ort.InferenceSession", lambda path: mock_session)

    image, keypoints = run_inference(img_path, model_path="fake.onnx")

    assert len(keypoints) == 17
    assert all(len(kp) == 3 for kp in keypoints)
    assert isinstance(image, np.ndarray)
