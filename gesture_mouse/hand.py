"""MediaPipe 手部 21 個關鍵點的編號與幾何工具。

座標使用 MediaPipe 的正規化座標 (x, y, z)，x、y 介於 0~1，原點在畫面左上角。
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

Point = Tuple[float, float, float]
Landmarks = Sequence[Point]

WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

# 四隻手指（不含拇指）的 (PIP, TIP) 編號
FINGERS = {
    "index": (INDEX_PIP, INDEX_TIP),
    "middle": (MIDDLE_PIP, MIDDLE_TIP),
    "ring": (RING_PIP, RING_TIP),
    "pinky": (PINKY_PIP, PINKY_TIP),
}

# 畫骨架用的連線
CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
]


def distance(a: Point, b: Point, aspect: float = 1.0) -> float:
    """兩點的 2D 距離。aspect = 畫面寬/高，用來修正正規化座標的長寬比。"""
    dx = (a[0] - b[0]) * aspect
    dy = a[1] - b[1]
    return math.hypot(dx, dy)


def hand_size(lm: Landmarks, aspect: float = 1.0) -> float:
    """以手腕到中指根部的距離當作手的大小，讓判斷不受手離鏡頭遠近影響。"""
    return max(distance(lm[WRIST], lm[MIDDLE_MCP], aspect), 1e-6)


def is_finger_extended(lm: Landmarks, finger: str, aspect: float = 1.0, ratio: float = 1.1) -> bool:
    """指尖離手腕比第二指節（PIP）離手腕還遠一定比例，就當作手指伸直。

    這種判斷方式不受手掌旋轉角度影響。
    """
    pip, tip = FINGERS[finger]
    wrist = lm[WRIST]
    return distance(wrist, lm[tip], aspect) > distance(wrist, lm[pip], aspect) * ratio


def near_edge(lm: Landmarks, margin: float = 0.03) -> bool:
    """手的任何關鍵點太靠近鏡頭畫面邊緣（快要離開畫面）。"""
    return any(p[0] < margin or p[0] > 1 - margin or p[1] < margin or p[1] > 1 - margin for p in lm)
