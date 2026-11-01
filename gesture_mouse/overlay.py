"""游標旁的狀態小圓圈。

不開預覽視窗也能知道系統怎麼解讀你的手：
綠 = 移動、橘 = 捏合判斷中、紅橘 = 拖曳、藍 = 捲動、紫 = 視窗手勢（三指）、白 = 抬起（握拳）、
紅 = 暫停、灰 = 看不到手、黃色閃爍 = 手快離開鏡頭畫面。

視窗是透明、置頂、滑鼠可穿透的，不會擋到點擊。目前只支援 Windows。
"""

from __future__ import annotations

import sys
from typing import Optional, Tuple

from .config import OverlayConfig
from .controller import Controller

COLORS = {
    "move": "#2ecc40",
    "pinch": "#ff9f1a",
    "drag": "#ff5a1f",
    "scroll": "#2f80ff",
    "lift": "#f5f5f5",
    "paused": "#e8262e",
    "nohand": "#8a8a8a",
    "idle": "#c8c8c8",
    "warning": "#ffd400",
    "windows": "#b04aff",
}

_TRANSPARENT = "#ff00ff"


def overlay_status(ctrl: Controller, hand_present: bool, near_edge: bool) -> str:
    """依控制器目前狀態決定圓圈要顯示哪一種狀態。"""
    if ctrl.paused:
        return "paused"
    if not hand_present:
        return "scroll" if ctrl.inertia_active else "nohand"
    if near_edge:
        return "warning"
    action = ctrl.current_action()
    if action == "pinch_smart":
        return "drag" if ctrl.smart_state == "drag" else "pinch"
    if action in ("hold_left", "hold_right"):
        return "drag"
    if action in ("click_left", "click_right", "double_click"):
        return "pinch"
    if action in ("scroll", "flick_scroll") or ctrl.inertia_active:
        return "scroll"
    if action == "flick_windows":
        return "windows"
    if action in ("move_cursor", "move_flick_scroll"):
        return "move"
    if action == "toggle_pause":
        return "lift"
    return "idle"


def is_visible(status: str, t: float) -> bool:
    """警告狀態每 0.25 秒閃爍一次，其他狀態一直顯示。"""
    if status != "warning":
        return True
    return int(t / 0.25) % 2 == 0


class CursorOverlay:
    def __init__(self, cfg: OverlayConfig) -> None:
        self.enabled = cfg.enabled and sys.platform == "win32"
        self.cfg = cfg
        self._root = None
        if not self.enabled:
            return
        try:
            self._create()
        except Exception as e:  # 圓圈失敗不影響控制
            print(f"無法建立狀態圓圈：{e}")
            self.enabled = False

    def _create(self) -> None:
        import ctypes
        import tkinter as tk

        size = self.cfg.size
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", _TRANSPARENT)
        root.configure(bg=_TRANSPARENT)
        canvas = tk.Canvas(root, width=size + 4, height=size + 4, bg=_TRANSPARENT, highlightthickness=0)
        canvas.pack()
        self._oval = canvas.create_oval(2, 2, size + 2, size + 2, fill=COLORS["idle"], outline="#202020", width=1)
        root.update_idletasks()

        # 滑鼠可穿透、不搶焦點、不出現在工作列
        GWL_EXSTYLE = -20
        WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80000, 0x20
        WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x08000000
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(root.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        )
        self._root, self._canvas, self._shown = root, canvas, True

    def update(self, status: str, cursor_pos: Optional[Tuple[int, int]], t: float) -> None:
        if not self.enabled or self._root is None:
            return
        try:
            visible = is_visible(status, t) and cursor_pos is not None
            if visible:
                x, y = cursor_pos
                self._root.geometry(f"+{int(x) + self.cfg.offset}+{int(y) + self.cfg.offset}")
                self._canvas.itemconfigure(self._oval, fill=COLORS[status])
                if not self._shown:
                    self._root.deiconify()
                    self._shown = True
            elif self._shown:
                self._root.withdraw()
                self._shown = False
            self._root.update()
        except Exception as e:
            print(f"狀態圓圈發生錯誤，已關閉：{e}")
            self.close()

    def close(self) -> None:
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
        self._root = None
        self.enabled = False
