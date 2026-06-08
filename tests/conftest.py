import numpy as np
import pytest


@pytest.fixture
def blank_image() -> np.ndarray:
    """640x480 solid-gray BGR image."""
    return np.full((480, 640, 3), 128, dtype=np.uint8)


@pytest.fixture
def dummy_keypoints() -> list[tuple[int, int, float]]:
    """17 keypoints at (100, 100) with confidence 0.9."""
    return [(100, 100, 0.9)] * 17
