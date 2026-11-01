"""規則式手勢判斷：把一幀的手部關鍵點轉成一個手勢。"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from . import hand
from .hand import Landmarks


class Gesture(str, Enum):
    NONE = "none"                  # 沒有手，或手勢不明
    PALM = "palm"                  # 張開手掌（四指伸直）
    POINT = "point"                # 只伸出食指
    PINCH_INDEX = "pinch_index"    # 食指 + 拇指捏合
    PINCH_MIDDLE = "pinch_middle"  # 中指 + 拇指捏合
    TWO_FINGER = "two_finger"      # 食指 + 中指伸出（甩動捲動、上一頁 / 下一頁）
    THREE_FINGER = "three_finger"  # 食指 + 中指 + 無名指伸出（視窗手勢）
    FIST = "fist"                  # 握拳


class GestureClassifier:
    """判斷手勢。捏合判斷有遲滯（hysteresis）：捏合和放開用不同門檻，避免邊界抖動。

    門檻都是「指尖距離 / 手的大小」的比例。
    """

    def __init__(
        self,
        pinch_enter: float = 0.25,
        pinch_exit: float = 0.35,
        extend_ratio: float = 1.1,
    ) -> None:
        if pinch_exit < pinch_enter:
            raise ValueError("pinch_exit 必須大於等於 pinch_enter")
        self.pinch_enter = pinch_enter
        self.pinch_exit = pinch_exit
        self.extend_ratio = extend_ratio
        self._pinching: Optional[Gesture] = None

    def reset(self) -> None:
        self._pinching = None

    def _pinch_ratio(self, lm: Landmarks, tip: int, aspect: float) -> float:
        return hand.distance(lm[hand.THUMB_TIP], lm[tip], aspect) / hand.hand_size(lm, aspect)

    def classify(self, lm: Optional[Landmarks], aspect: float = 1.0) -> Gesture:
        if lm is None:
            self.reset()
            return Gesture.NONE
        if len(lm) != 21:
            raise ValueError(f"需要 21 個關鍵點，收到 {len(lm)} 個")

        ext = {f: hand.is_finger_extended(lm, f, aspect, self.extend_ratio) for f in hand.FINGERS}

        # 1. 握拳：四指都彎曲
        if not any(ext.values()):
            self.reset()
            return Gesture.FIST

        # 2. 捏合（含遲滯）
        index_ratio = self._pinch_ratio(lm, hand.INDEX_TIP, aspect)
        middle_ratio = self._pinch_ratio(lm, hand.MIDDLE_TIP, aspect)

        if self._pinching == Gesture.PINCH_INDEX and index_ratio < self.pinch_exit:
            return Gesture.PINCH_INDEX
        if self._pinching == Gesture.PINCH_MIDDLE and middle_ratio < self.pinch_exit:
            return Gesture.PINCH_MIDDLE
        self._pinching = None

        if index_ratio < self.pinch_enter and index_ratio <= middle_ratio:
            self._pinching = Gesture.PINCH_INDEX
            return Gesture.PINCH_INDEX
        if middle_ratio < self.pinch_enter:
            self._pinching = Gesture.PINCH_MIDDLE
            return Gesture.PINCH_MIDDLE

        # 3. 雙指：食指、中指伸直，無名指、小指彎曲
        if ext["index"] and ext["middle"] and not ext["ring"] and not ext["pinky"]:
            return Gesture.TWO_FINGER

        # 4. 三指：食指、中指、無名指伸直，小指彎曲
        if ext["index"] and ext["middle"] and ext["ring"] and not ext["pinky"]:
            return Gesture.THREE_FINGER

        # 5. 張開手掌：四指都伸直
        if all(ext.values()):
            return Gesture.PALM

        # 6. 只有食指伸直
        if ext["index"] and not ext["middle"] and not ext["ring"] and not ext["pinky"]:
            return Gesture.POINT

        return Gesture.NONE
