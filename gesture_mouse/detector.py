"""MediaPipe 手部偵測，輸出 21 個關鍵點。

新版 MediaPipe 可能拿掉了舊的 `mp.solutions.hands`，所以兩種 API 都支援：
1. 有 `mp.solutions.hands` 就直接用（不用下載模型）。
2. 沒有的話改用 Tasks API，第一次執行會自動下載模型到 models/ 資料夾。
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import List, Optional

from .hand import DetectedHand, Point

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"


class HandDetector:
    def __init__(
        self,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.6,
        mirrored: bool = True,
        swap_hands: bool = False,
    ) -> None:
        import mediapipe as mp

        self._mirrored = mirrored
        self._swap_override = swap_hands

        self._mp = mp
        solutions = getattr(mp, "solutions", None)
        if solutions is not None and hasattr(solutions, "hands"):
            self._mode = "solutions"
            self._hands = solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
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
                # 用 bytes 載入：MediaPipe 的 C++ 層無法開啟含中文等非 ASCII 字元的路徑
                base_options=BaseOptions(model_asset_buffer=MODEL_PATH.read_bytes()),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=min_detection_confidence,
                min_hand_presence_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self._hands = vision.HandLandmarker.create_from_options(options)

        # 左右手標籤：舊版 solutions API 假設畫面是鏡像的；新版 Tasks API（實測 1.2.0）
        # 則是以沒翻轉的畫面為準。依目前是否翻轉畫面決定要不要對調，設定檔可再強制對調。
        if self._mode == "tasks":
            swap = self._mirrored
        else:
            swap = not self._mirrored
        self._swap_sides = swap != self._swap_override

    def detect(self, rgb_frame, timestamp_ms: int) -> Optional[List[Point]]:
        """回傳第一隻手的 21 個 (x, y, z)，沒偵測到就回傳 None。"""
        hands = self.detect_hands(rgb_frame, timestamp_ms)
        return hands[0].landmarks if hands else None

    def _side(self, label: str) -> str:
        side = "right" if label.lower() == "right" else "left"
        if self._swap_sides:
            side = "left" if side == "right" else "right"
        return side

    def detect_hands(self, rgb_frame, timestamp_ms: int) -> List[DetectedHand]:
        """輸入 RGB 影像，回傳畫面上所有手（最多兩隻）的關鍵點與左右手。"""
        if self._mode == "solutions":
            result = self._hands.process(rgb_frame)
            if not result.multi_hand_landmarks:
                return []
            out = []
            for i, hand_lm in enumerate(result.multi_hand_landmarks):
                cls = result.multi_handedness[i].classification[0] if result.multi_handedness else None
                out.append(DetectedHand(
                    [(p.x, p.y, p.z) for p in hand_lm.landmark],
                    self._side(cls.label if cls else "right"),
                    float(cls.score) if cls else 1.0,
                ))
            return out

        # MediaPipe 要求時間戳嚴格遞增；同一毫秒內兩幀會讓它丟例外
        last = getattr(self, "_last_ts", -1)
        if timestamp_ms <= last:
            timestamp_ms = last + 1
        self._last_ts = timestamp_ms
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._hands.detect_for_video(image, timestamp_ms)
        out = []
        for i, hand_lm in enumerate(result.hand_landmarks or []):
            cat = result.handedness[i][0] if result.handedness and result.handedness[i] else None
            out.append(DetectedHand(
                [(p.x, p.y, p.z) for p in hand_lm],
                self._side(cat.category_name if cat else "right"),
                float(cat.score) if cat else 1.0,
            ))
        return out

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
