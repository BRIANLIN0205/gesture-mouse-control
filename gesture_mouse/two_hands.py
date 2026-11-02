"""雙手動作：兩手縮放、另一隻手（預設左手）調音量。

和 Controller 一樣只回傳指令，不直接碰滑鼠鍵盤，方便測試。
- 縮放：兩手都用食指捏拇指，拉開 = 放大、靠近 = 縮小（Ctrl + 滾輪）。縮放時主控手的點擊 / 拖曳會先取消。
- 音量：另一隻手中指捏拇指，往上移 = 音量變大、往下 = 變小，離起點越遠調越快。
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .config import TwoHandsConfig
from .controller import Command, Hotkey, Zoom
from .gestures import Gesture
from .hand import INDEX_TIP, MIDDLE_MCP, THUMB_TIP, Landmarks

VOLUME_UP = Hotkey(("volume_up",), "volume_up")
VOLUME_DOWN = Hotkey(("volume_down",), "volume_down")


def _pinch_point(lm: Landmarks) -> Tuple[float, float]:
    """食指和拇指指尖的中點。"""
    return (lm[THUMB_TIP][0] + lm[INDEX_TIP][0]) / 2, (lm[THUMB_TIP][1] + lm[INDEX_TIP][1]) / 2


class TwoHandController:
    def __init__(self, cfg: TwoHandsConfig, stable_frames: int = 2) -> None:
        self.cfg = cfg
        self.stable_frames = max(1, stable_frames)
        # 縮放
        self.zooming = False
        self.main_blocked = False   # 縮放後主控手還捏著：先不理它，放開後才恢復（避免放開時誤點）
        self._zoom_count = 0
        self._zoom_ref: Optional[float] = None
        # 音量
        self.volume_active = False
        self._vol_count = 0
        self._vol_origin: Optional[float] = None
        self._vol_last_t: Optional[float] = None
        self._vol_rem = 0.0
        self._vol_engaged = False   # 已超出死區，正在調整

    def update(
        self,
        main_gesture: Gesture,
        main_lm: Optional[Landmarks],
        other_gesture: Gesture,
        other_lm: Optional[Landmarks],
        t: float,
        aspect: float = 1.0,
        paused: bool = False,
    ) -> List[Command]:
        cmds: List[Command] = []
        if paused:
            self._stop_zoom()
            self._stop_volume()
            self.main_blocked = False
            return cmds

        both_pinch = (
            self.cfg.zoom
            and main_lm is not None and other_lm is not None
            and main_gesture == Gesture.PINCH_INDEX and other_gesture == Gesture.PINCH_INDEX
        )
        self._zoom_count = self._zoom_count + 1 if both_pinch else 0
        if self._zoom_count >= self.stable_frames:
            self._zoom(main_lm, other_lm, aspect, cmds)
        else:
            self._stop_zoom()
        if self.zooming:
            self.main_blocked = True
        elif main_gesture != Gesture.PINCH_INDEX:
            self.main_blocked = False

        vol = (
            self.cfg.volume and not self.zooming
            and other_lm is not None and other_gesture == Gesture.PINCH_MIDDLE
        )
        self._vol_count = self._vol_count + 1 if vol else 0
        if self._vol_count >= self.stable_frames:
            self._volume(other_lm, t, cmds)
        else:
            self._stop_volume()
        return cmds

    # ---------- 縮放 ----------

    def _zoom(self, a: Landmarks, b: Landmarks, aspect: float, cmds: List[Command]) -> None:
        pa, pb = _pinch_point(a), _pinch_point(b)
        d = max(math.hypot((pa[0] - pb[0]) * aspect, pa[1] - pb[1]), 1e-6)
        self.zooming = True
        if self._zoom_ref is None:
            self._zoom_ref = d
            return
        step = math.log(1 + max(self.cfg.zoom_step, 1e-3))
        n = int(math.log(d / self._zoom_ref) / step)   # 往 0 取整：要真的變化一整格才縮放
        if n:
            self._zoom_ref *= math.exp(n * step)
            cmds.append(Zoom(n))

    def _stop_zoom(self) -> None:
        self.zooming = False
        self._zoom_ref = None

    # ---------- 音量 ----------

    def _volume(self, lm: Landmarks, t: float, cmds: List[Command]) -> None:
        c = self.cfg
        y = lm[MIDDLE_MCP][1]
        self.volume_active = True
        if self._vol_origin is None:
            self._vol_origin = y
            self._vol_last_t = t
            return
        dt = t - (self._vol_last_t if self._vol_last_t is not None else t)
        self._vol_last_t = t
        dy = y - self._vol_origin
        if abs(dy) <= c.volume_deadzone:
            self._vol_engaged = False
            return
        key = VOLUME_UP if dy < 0 else VOLUME_DOWN   # 手往上 = 變大
        if not self._vol_engaged:
            self._vol_engaged = True     # 剛超過死區就先調一下，反應比較快
            self._vol_rem = 0.0
            cmds.append(key)
            return
        span = max(c.volume_full - c.volume_deadzone, 1e-6)
        k = min(1.0, (abs(dy) - c.volume_deadzone) / span)
        self._vol_rem += c.volume_max_speed * k * dt
        n = int(self._vol_rem)
        if n:
            self._vol_rem -= n
            cmds.extend([key] * n)

    def _stop_volume(self) -> None:
        self.volume_active = False
        self._vol_engaged = False
        self._vol_origin = None
        self._vol_last_t = None
        self._vol_rem = 0.0
