"""MediaPipe 手部偵測，輸出 21 個關鍵點。

新版 MediaPipe 可能拿掉了舊的 `mp.solutions.hands`，所以兩種 API 都支援：
1. 有 `mp.solutions.hands` 就直接用（不用下載模型）。
2. 沒有的話改用 Tasks API，第一次執行會自動下載模型到 models/ 資料夾。
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import List, Optional

from .hand import Point

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"


class HandDetector:
    def __init__(self, min_detection_confidence: float = 0.7, min_tracking_confidence: float = 0.6) -> None:
        import mediapipe as mp

        self._mp = mp
        solutions = getattr(mp, "solutions", None)
        if solutions is not None and hasattr(solutions, "hands"):
            self._mode = "solutions"
            self._hands = solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=1,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        else:
            self._mode = "tasks"
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python import vision

            _ensure_model()
            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=min_detection_confidence,
                min_hand_presence_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self._hands = vision.HandLandmarker.create_from_options(options)

    def detect(self, rgb_frame, timestamp_ms: int) -> Optional[List[Point]]:
        """輸入 RGB 影像，回傳第一隻手的 21 個 (x, y, z)，沒偵測到就回傳 None。"""
        if self._mode == "solutions":
            result = self._hands.process(rgb_frame)
            if not result.multi_hand_landmarks:
                return None
            return [(p.x, p.y, p.z) for p in result.multi_hand_landmarks[0].landmark]

        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._hands.detect_for_video(image, timestamp_ms)
        if not result.hand_landmarks:
            return None
        return [(p.x, p.y, p.z) for p in result.hand_landmarks[0]]

    def close(self) -> None:
        self._hands.close()


def _ensure_model() -> None:
    if MODEL_PATH.exists():
        return
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"第一次執行，下載手部模型到 {MODEL_PATH} ...")
    tmp = MODEL_PATH.with_suffix(".part")
    urllib.request.urlretrieve(MODEL_URL, tmp)
    tmp.replace(MODEL_PATH)
