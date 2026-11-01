"""把每一幀的手勢轉成滑鼠指令。

這一層不直接碰滑鼠，只回傳指令清單，方便單元測試。
真正送出指令的是 mouse.py。
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

from .config import Config
from .gestures import Gesture
from .hand import Landmarks, INDEX_TIP, MIDDLE_MCP, MIDDLE_TIP
from .smoothing import PointFilter


@dataclass(frozen=True)
class MoveTo:
    x: int
    y: int


@dataclass(frozen=True)
class MoveBy:
    dx: int
    dy: int


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


@dataclass(frozen=True)
class PauseChanged:
    paused: bool  # True = 剛暫停，False = 剛恢復（用來播音效）


@dataclass(frozen=True)
class Hotkey:
    keys: Tuple[str, ...]  # 例如 ("alt", "left")；同時按下再依反序放開
    name: str = ""         # 給教學 / 記錄用的名稱，例如 "back"


# 甩動方向 → 快捷鍵
FLICK_NAV = {
    "left": Hotkey(("alt", "left"), "back"),        # 上一頁
    "right": Hotkey(("alt", "right"), "forward"),   # 下一頁
}
FLICK_WINDOWS = {
    "up": Hotkey(("win", "tab"), "task_view"),          # 所有視窗
    "down": Hotkey(("win", "d"), "show_desktop"),       # 顯示桌面
    "left": Hotkey(("alt", "shift", "tab"), "prev_window"),
    "right": Hotkey(("alt", "tab"), "next_window"),
}

Command = object

# 這些動作進行中會帶動游標
_POINTER_ACTIONS = ("move_cursor", "move_flick_scroll", "hold_left", "hold_right", "pinch_smart")
# 這些動作開始時要鎖住游標，避免捏合時手抖把點擊點歪
_CLICK_ACTIONS = ("hold_left", "hold_right", "click_left", "click_right", "double_click", "pinch_smart")


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
        # 相對模式
        self._last_ptr: Optional[Tuple[float, float]] = None
        self._last_t: Optional[float] = None
        self._move_rem = [0.0, 0.0]
        # 點擊鎖定
        self._lock_until = 0.0
        # 捲動速度與慣性（單位：格 / 秒）
        self._scroll_v = 0.0
        self._scroll_last_t: Optional[float] = None
        self._inertia_v = 0.0
        self._inertia_rem = 0.0
        self._last_update_t: Optional[float] = None
        # pinch_smart 狀態：None / "pending"（還不知道是點擊、拖曳或右鍵）/ "drag" / "done"
        self.smart_state: Optional[str] = None
        self._smart_start = 0.0
        self._smart_acc = [0.0, 0.0]
        self._smart_abs_start: Optional[Tuple[int, int]] = None
        self._hand_lost = False
        # 甩動偵測：最近 0.2 秒手掌中心的位置
        self._swipe_hist: Deque[Tuple[float, float, float]] = deque()
        self._swipe_block_until = 0.0
        self.last_flick: Optional[str] = None   # 最近一次甩動（給教學 / 狀態顯示用）

    # ---------- 對外介面 ----------

    def update(self, gesture: Gesture, lm: Optional[Landmarks], t: float) -> List[Command]:
        """輸入這一幀的手勢、關鍵點與時間（秒），回傳要執行的滑鼠指令。"""
        cmds: List[Command] = []

        self._hand_lost = lm is None
        if lm is None:
            gesture = Gesture.NONE
            self._reset_pointer()

        stable = self._debounce(gesture)

        if stable != self.active:
            # 從非移動類手勢切進移動類（例如捲動 → 移動）時重新起算，避免游標跳動；
            # 移動 ↔ 捏合拖曳之間則保持連續。
            if self._action(stable) in _POINTER_ACTIONS and self._action(self.active) not in _POINTER_ACTIONS:
                self._reset_pointer()
            self._exit(self.active, cmds)
            self.active = stable
            self._enter(stable, lm, t, cmds)

        self._during(stable, lm, t, cmds)
        self._run_inertia(t, cmds)
        self._last_update_t = t
        return cmds

    def current_action(self) -> str:
        """目前生效手勢對應的動作（暫停時只有 toggle_pause 有效）。"""
        return self._action(self.active)

    @property
    def inertia_active(self) -> bool:
        return self._inertia_v != 0.0

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
        elif action == "pinch_smart":
            self.smart_state = "pending"
            self._smart_start = t
            self._smart_acc = [0.0, 0.0]
            self._smart_abs_start = None
        elif action == "scroll":
            self._scroll_ref = self._scroll_y(lm) if lm is not None else None
            self._scroll_accum = 0.0
            self._scroll_v = 0.0
            self._scroll_last_t = t
        elif action == "toggle_pause":
            self._pause_start = t
            self._pause_toggled = False
        elif action in ("flick_scroll", "flick_windows", "move_flick_scroll"):
            self._swipe_hist.clear()
        if action in _CLICK_ACTIONS:
            self._lock_until = t + self.cfg.control.click_lock_seconds
        if action == "scroll" or action in _CLICK_ACTIONS:
            self._stop_inertia()   # 再次捲動或點擊時停止慣性（像觸控板手指一碰就停）

    def _reset_pointer(self) -> None:
        """手離開或換手勢時呼叫：下次移動重新起算，游標不會跳。"""
        self.filter.reset()
        self._last_ptr = None
        self._last_t = None
        self._move_rem = [0.0, 0.0]

    def _exit(self, gesture: Gesture, cmds: List[Command]) -> None:
        # 輕捏後放開（沒移動、沒捏太久）= 左鍵點擊；手直接離開畫面則不算
        if self.smart_state == "pending" and not self._hand_lost:
            cmds.append(Click("left"))
        self.smart_state = None
        self._release_held(cmds)
        if self._scroll_ref is not None:
            self._start_inertia()
        self._scroll_ref = None
        self._pause_start = None

    def _during(self, gesture: Gesture, lm: Optional[Landmarks], t: float, cmds: List[Command]) -> None:
        action = self._action(gesture)
        if lm is None:
            return

        if action == "pinch_smart":
            self._during_smart(lm, t, cmds)
        elif action in _POINTER_ACTIONS:
            cmd = self._move(lm, t)   # 鎖定時仍要更新位置，解鎖後才不會跳
            if cmd is not None and not self._cursor_locked(t):
                cmds.append(cmd)
            if action == "move_flick_scroll":
                # 手掌快速上下甩 = 捲動、左右甩 = 上一頁 / 下一頁（游標照常移動，留在甩完的位置）
                direction, speed = self._detect_swipe(
                    lm, t, self.cfg.control.palm_swipe_min_speed,
                    vertical_only=not self.cfg.control.palm_flick_nav,
                )
                if direction:
                    self._on_flick("flick_scroll", direction, speed, cmds)
        elif action == "scroll":
            self._scroll(lm, t, cmds)
        elif action in ("flick_scroll", "flick_windows"):
            direction, speed = self._detect_swipe(lm, t)
            if direction:
                self._on_flick(action, direction, speed, cmds)
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
                cmds.append(PauseChanged(self.paused))

    def _move(self, lm: Landmarks, t: float):
        p = lm[self.cfg.cursor.pointer_landmark]
        if self.cfg.cursor.mode == "absolute":
            x, y = self.to_screen(p)
            sx, sy = self.filter(x, y, t)
            sx = min(max(sx, 0), self.screen_w - 1)
            sy = min(max(sy, 0), self.screen_h - 1)
            return MoveTo(int(round(sx)), int(round(sy)))
        return self._move_relative(p, t)

    def _move_relative(self, p, t: float) -> Optional[MoveBy]:
        """相對移動：手在鏡頭畫面中的位移 × 倍率 = 游標位移（倍率隨速度增加）。"""
        c = self.cfg.cursor
        # 以螢幕像素為單位（手移過整個鏡頭畫面 = 一個螢幕寬/高），再平滑
        fx, fy = self.filter(p[0] * self.screen_w, p[1] * self.screen_h, t)
        last, last_t = self._last_ptr, self._last_t
        self._last_ptr, self._last_t = (fx, fy), t
        if last is None or last_t is None:
            return None

        dx, dy = fx - last[0], fy - last[1]
        dt = max(t - last_t, 1e-3)
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < c.relative_deadzone:
            return None

        # 速度以「每秒移動幾個螢幕寬」計
        speed = dist / self.screen_w / dt
        gain = min(c.relative_gain * (1 + c.relative_accel * speed), c.relative_max_gain)

        self._move_rem[0] += dx * gain
        self._move_rem[1] += dy * gain
        mx, my = int(self._move_rem[0]), int(self._move_rem[1])
        self._move_rem[0] -= mx
        self._move_rem[1] -= my
        if mx == 0 and my == 0:
            return None
        return MoveBy(mx, my)

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

    def _during_smart(self, lm: Landmarks, t: float, cmds: List[Command]) -> None:
        cmd = self._move(lm, t)
        locked = self._cursor_locked(t)
        c = self.cfg.control
        if self.smart_state == "drag":
            if cmd is not None and not locked:
                cmds.append(cmd)
            return
        if self.smart_state != "pending":
            return  # 已經觸發右鍵，等放開
        # 還在判斷中：游標不動，只累計手的位移（鎖定期間的抖動不算）
        dist = 0.0
        if cmd is not None and not locked:
            if isinstance(cmd, MoveBy):
                self._smart_acc[0] += cmd.dx
                self._smart_acc[1] += cmd.dy
                dist = math.hypot(*self._smart_acc)
            elif isinstance(cmd, MoveTo):
                if self._smart_abs_start is None:
                    self._smart_abs_start = (cmd.x, cmd.y)
                dist = math.hypot(cmd.x - self._smart_abs_start[0], cmd.y - self._smart_abs_start[1])
        if dist >= c.drag_threshold_px:
            # 開始拖曳：在原地按下左鍵，再補上已經移動的距離
            self.smart_state = "drag"
            self._held = "left"
            cmds.append(Press("left"))
            if isinstance(cmd, MoveTo):
                cmds.append(cmd)
            else:
                cmds.append(MoveBy(int(self._smart_acc[0]), int(self._smart_acc[1])))
        elif t - self._smart_start >= c.right_hold_seconds:
            self.smart_state = "done"
            cmds.append(Click("right"))

    def _cursor_locked(self, t: float) -> bool:
        """點擊開始後一小段時間，或手勢正要切換成點擊 / 從點擊切回來時，游標不動。"""
        if t < self._lock_until:
            return True
        pending = self._candidate != self.active and self._candidate_count > 0
        if pending and (
            self._action(self._candidate) in _CLICK_ACTIONS or self._action(self.active) in _CLICK_ACTIONS
        ):
            return True
        return False

    # ---------- 甩動 ----------

    _SWIPE_WINDOW = 0.2

    def _detect_swipe(
        self, lm: Landmarks, t: float, min_speed: Optional[float] = None, vertical_only: bool = False
    ) -> Tuple[Optional[str], float]:
        """用手掌中心（中指根部）最近 0.2 秒的位移判斷是否快速甩動。回傳 (方向, 速度)。"""
        c = self.cfg.control
        if min_speed is None:
            min_speed = c.swipe_min_speed
        p = lm[MIDDLE_MCP]
        hist = self._swipe_hist
        hist.append((t, p[0], p[1]))
        while hist and t - hist[0][0] > self._SWIPE_WINDOW:
            hist.popleft()
        if t < self._swipe_block_until or len(hist) < 2:
            return None, 0.0
        t0, x0, y0 = hist[0]
        dt = t - t0
        if dt <= 0:
            return None, 0.0
        dx, dy = p[0] - x0, p[1] - y0
        dist = math.hypot(dx, dy)
        speed = dist / dt
        if dist < c.swipe_min_distance or speed < min_speed:
            return None, 0.0
        # 主要方向要明顯（避免斜甩被亂判）
        if abs(dy) >= abs(dx) * 1.5:
            direction = "up" if dy < 0 else "down"
        elif abs(dx) >= abs(dy) * 1.5 and not vertical_only:
            direction = "left" if dx < 0 else "right"
        else:
            return None, 0.0
        # 捲動力道用「最近一小段」的速度，比較接近甩動當下的快慢
        recent = [h for h in hist if t - h[0] <= 0.07] or [hist[-2]]
        if recent[0][0] < t:
            rt, rx, ry = recent[0]
            speed = max(speed, math.hypot(p[0] - rx, p[1] - ry) / (t - rt))
        hist.clear()
        self._swipe_block_until = t + c.swipe_cooldown
        return direction, speed

    def _on_flick(self, action: str, direction: str, speed: float, cmds: List[Command]) -> None:
        self.last_flick = direction
        if action == "flick_windows":
            cmds.append(FLICK_WINDOWS[direction])
            return
        if direction in FLICK_NAV:
            cmds.append(FLICK_NAV[direction])
            return
        # 上下甩 = 捲動：給一個初速，之後靠慣性慢慢停下
        v = speed * self.cfg.control.flick_scroll_gain
        if direction == "down":
            v = -v                      # 手往上甩 = 往上捲
        if self.cfg.control.scroll_invert:
            v = -v
        if self._inertia_v and (self._inertia_v > 0) == (v > 0):
            v += self._inertia_v        # 同方向連續甩，越甩越快
        self._inertia_v = v
        self._inertia_rem = 0.0
        # 第一格立刻捲，手感比較即時
        first = 1 if v > 0 else -1
        cmds.append(Scroll(first))

    # ---------- 捲動慣性 ----------

    def _start_inertia(self) -> None:
        c = self.cfg.control
        if c.scroll_inertia and abs(self._scroll_v) >= c.scroll_inertia_min_speed:
            self._inertia_v = self._scroll_v
            self._inertia_rem = 0.0

    def _stop_inertia(self) -> None:
        self._inertia_v = 0.0
        self._inertia_rem = 0.0

    def _run_inertia(self, t: float, cmds: List[Command]) -> None:
        if self._inertia_v == 0.0 or self._last_update_t is None:
            return
        if self.paused:
            self._stop_inertia()
            return
        dt = max(t - self._last_update_t, 0.0)
        self._inertia_v *= math.exp(-self.cfg.control.scroll_inertia_friction * dt)
        if abs(self._inertia_v) < 2.0:
            self._stop_inertia()
            return
        self._inertia_rem += self._inertia_v * dt
        steps = int(self._inertia_rem)
        if steps:
            self._inertia_rem -= steps
            cmds.append(Scroll(steps))

    def _scroll(self, lm: Landmarks, t: float, cmds: List[Command]) -> None:
        y = self._scroll_y(lm)
        if self._scroll_ref is None:
            self._scroll_ref = y
            self._scroll_last_t = t
            return
        # 手往上（y 變小）= 往上捲
        delta = (self._scroll_ref - y) * self.cfg.control.scroll_sensitivity
        if self.cfg.control.scroll_invert:
            delta = -delta
        self._scroll_ref = y
        # 速度（格 / 秒），約 0.1 秒的平滑，用來決定甩動慣性
        if self._scroll_last_t is not None and t > self._scroll_last_t:
            dt = t - self._scroll_last_t
            k = min(1.0, dt / 0.1)
            self._scroll_v += (delta / dt - self._scroll_v) * k
        self._scroll_last_t = t
        self._scroll_accum += delta
        steps = int(self._scroll_accum)
        if steps:
            self._scroll_accum -= steps
            cmds.append(Scroll(steps))
