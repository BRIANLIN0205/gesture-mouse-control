"""把每一幀的手勢轉成滑鼠指令。

這一層不直接碰滑鼠，只回傳指令清單，方便單元測試。
真正送出指令的是 mouse.py。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .config import Config
from .gestures import Gesture
from .hand import Landmarks, INDEX_TIP, MIDDLE_TIP
from .smoothing import PointFilter


@dataclass(frozen=True)
class MoveTo:
    x: int
    y: int


@dataclass(frozen=True)
class Press:
    button: str  # "left" / "right"


@dataclass(frozen=True)
class Release:
    button: str


@dataclass(frozen=True)
class Click:
    button: str
    count: int = 1


@dataclass(frozen=True)
class Scroll:
    steps: int  # 正數往上，負數往下


Command = object


class Controller:
    def __init__(self, config: Config, screen_size: Tuple[int, int]) -> None:
        self.cfg = config
        self.screen_w, self.screen_h = screen_size
        self.filter = PointFilter(config.cursor.smoothing_min_cutoff, config.cursor.smoothing_beta)

        self.paused = False
        self.active: Gesture = Gesture.NONE       # 目前生效的手勢
        self._candidate: Gesture = Gesture.NONE   # 等待確認的新手勢
        self._candidate_count = 0
        self._held: Optional[str] = None          # 目前按住的按鍵
        self._pause_start: Optional[float] = None
        self._pause_toggled = False
        self._scroll_ref: Optional[float] = None
        self._scroll_accum = 0.0

    # ---------- 對外介面 ----------

    def update(self, gesture: Gesture, lm: Optional[Landmarks], t: float) -> List[Command]:
        """輸入這一幀的手勢、關鍵點與時間（秒），回傳要執行的滑鼠指令。"""
        cmds: List[Command] = []

        if lm is None:
            gesture = Gesture.NONE
            self.filter.reset()

        stable = self._debounce(gesture)

        if stable != self.active:
            self._exit(self.active, cmds)
            self.active = stable
            self._enter(stable, lm, t, cmds)

        self._during(stable, lm, t, cmds)
        return cmds

    def release_all(self) -> List[Command]:
        """程式結束時呼叫，確保不會留下按住的按鍵。"""
        cmds: List[Command] = []
        self._release_held(cmds)
        return cmds

    # ---------- 內部 ----------

    def _debounce(self, gesture: Gesture) -> Gesture:
        n = max(1, self.cfg.control.stable_frames)
        if gesture == self.active:
            self._candidate, self._candidate_count = gesture, 0
            return self.active
        if gesture == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate, self._candidate_count = gesture, 1
        if self._candidate_count >= n:
            self._candidate_count = 0
            return gesture
        return self.active

    def _action(self, gesture: Gesture) -> str:
        if gesture == Gesture.NONE:
            return "none"
        action = self.cfg.action_for(gesture)
        # 暫停時只接受切換暫停的手勢
        if self.paused and action != "toggle_pause":
            return "none"
        return action

    def _release_held(self, cmds: List[Command]) -> None:
        if self._held:
            cmds.append(Release(self._held))
            self._held = None

    def _enter(self, gesture: Gesture, lm: Optional[Landmarks], t: float, cmds: List[Command]) -> None:
        action = self._action(gesture)
        if action == "hold_left":
            self._held = "left"
            cmds.append(Press("left"))
        elif action == "hold_right":
            self._held = "right"
            cmds.append(Press("right"))
        elif action == "click_left":
            cmds.append(Click("left"))
        elif action == "click_right":
            cmds.append(Click("right"))
        elif action == "double_click":
            cmds.append(Click("left", 2))
        elif action == "scroll":
            self._scroll_ref = self._scroll_y(lm) if lm is not None else None
            self._scroll_accum = 0.0
        elif action == "toggle_pause":
            self._pause_start = t
            self._pause_toggled = False

    def _exit(self, gesture: Gesture, cmds: List[Command]) -> None:
        self._release_held(cmds)
        self._scroll_ref = None
        self._pause_start = None

    def _during(self, gesture: Gesture, lm: Optional[Landmarks], t: float, cmds: List[Command]) -> None:
        action = self._action(gesture)
        if lm is None:
            return

        if action in ("move_cursor", "hold_left", "hold_right"):
            cmds.append(self._move(lm, t))
        elif action == "scroll":
            self._scroll(lm, cmds)
        elif action == "toggle_pause":
            if (
                self._pause_start is not None
                and not self._pause_toggled
                and t - self._pause_start >= self.cfg.control.pause_hold_seconds
            ):
                self._pause_toggled = True
                self.paused = not self.paused
                if self.paused:
                    self._release_held(cmds)

    def _move(self, lm: Landmarks, t: float) -> MoveTo:
        x, y = self.to_screen(lm[self.cfg.cursor.pointer_landmark])
        sx, sy = self.filter(x, y, t)
        sx = min(max(sx, 0), self.screen_w - 1)
        sy = min(max(sy, 0), self.screen_h - 1)
        return MoveTo(int(round(sx)), int(round(sy)))

    def to_screen(self, point) -> Tuple[float, float]:
        """把鏡頭畫面上的正規化座標對應到螢幕像素（扣掉四周留白）。"""
        m = self.cfg.cursor.frame_margin
        span = max(1e-6, 1 - 2 * m)
        nx = min(max((point[0] - m) / span, 0.0), 1.0)
        ny = min(max((point[1] - m) / span, 0.0), 1.0)
        return nx * (self.screen_w - 1), ny * (self.screen_h - 1)

    @staticmethod
    def _scroll_y(lm: Landmarks) -> float:
        return (lm[INDEX_TIP][1] + lm[MIDDLE_TIP][1]) / 2

    def _scroll(self, lm: Landmarks, cmds: List[Command]) -> None:
        y = self._scroll_y(lm)
        if self._scroll_ref is None:
            self._scroll_ref = y
            return
        # 手往上（y 變小）= 往上捲
        delta = (self._scroll_ref - y) * self.cfg.control.scroll_sensitivity
        if self.cfg.control.scroll_invert:
            delta = -delta
        self._scroll_ref = y
        self._scroll_accum += delta
        steps = int(self._scroll_accum)
        if steps:
            self._scroll_accum -= steps
            cmds.append(Scroll(steps))
