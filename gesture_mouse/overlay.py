"""游標旁的狀態小圓圈。

不開預覽視窗也能知道系統怎麼解讀你的手：
綠 = 移動、橘 = 捏合判斷中、紅橘 = 拖曳、藍 = 捲動、紫 = 三指視窗選單、青 = 雙手縮放、粉紅 = 調音量、白 = 抬起（握拳）、
紅 = 暫停、灰 = 看不到手、黃色閃爍 = 手快離開鏡頭畫面。
伸出三指時，游標旁另外跳出十字選單（所有視窗 / 顯示桌面 / 上一個 / 下一個視窗），選到的那格會亮起來。

視窗是透明、置頂、滑鼠可穿透的，不會擋到點擊。目前只支援 Windows。
"""

from __future__ import annotations

import sys
from typing import Dict, Optional, Tuple

from .config import OverlayConfig
from .controller import MENU_LABELS, Controller

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
    "zoom": "#00c8c8",
    "volume": "#ff4fa3",
}

_TRANSPARENT = "#ff00ff"
_MENU_BG = "#2a2a2a"


def overlay_status(ctrl: Controller, hand_present: bool, near_edge: bool, two_hands=None) -> str:
    """依控制器目前狀態決定圓圈要顯示哪一種狀態。two_hands：TwoHandController（可省略）。"""
    if ctrl.paused:
        return "paused"
    if two_hands is not None and two_hands.zooming:
        return "zoom"
    if two_hands is not None and two_hands.volume_active:
        return "volume"
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
    if action in ("scroll", "flick_scroll", "joystick") or ctrl.inertia_active:
        return "scroll"
    if action in ("flick_windows", "menu_windows"):
        return "windows"
    if action in ("move_cursor", "move_flick_scroll"):
        return "move"
    if action == "toggle_pause":
        return "lift"
    return "idle"


# 十字選單每一格的大小與間距（像素）
MENU_CELL = (120, 40)
MENU_GAP = 6
MENU_DIRS = ("up", "down", "left", "right")


def menu_state(ctrl: Controller) -> Optional[str]:
    """三指選單目前的狀態：None = 不顯示、"center" = 顯示但還沒選、其他 = 選到的方向。"""
    if not ctrl.menu_active or ctrl.paused:
        return None
    return ctrl.menu_choice or "center"


def menu_boxes(cell: Tuple[int, int] = MENU_CELL, gap: int = MENU_GAP) -> Dict[str, Tuple[int, int, int, int]]:
    """十字選單各格在畫布上的位置 (x1, y1, x2, y2)，畫布中心就是選單中心。"""
    w, h = cell
    cx, cy = w * 1.5 + gap, h * 1.5 + gap
    def box(ox: float, oy: float) -> Tuple[int, int, int, int]:
        x, y = cx + ox * (w + gap), cy + oy * (h + gap)
        return int(x - w / 2), int(y - h / 2), int(x + w / 2), int(y + h / 2)
    return {"up": box(0, -1), "down": box(0, 1), "left": box(-1, 0), "right": box(1, 0), "center": box(0, 0)}


def menu_canvas_size(cell: Tuple[int, int] = MENU_CELL, gap: int = MENU_GAP) -> Tuple[int, int]:
    return int(cell[0] * 3 + gap * 2), int(cell[1] * 3 + gap * 2)


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
        # 滑鼠可穿透、不搶焦點、不出現在工作列（見 _make_click_through）
        self._root, self._canvas, self._shown = root, canvas, True
        self._make_click_through(root)
        self._create_menu(tk)

    @staticmethod
    def _make_click_through(win) -> None:
        import ctypes

        GWL_EXSTYLE = -20
        WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80000, 0x20
        WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x08000000
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(win.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        )

    def _create_menu(self, tk) -> None:
        """三指十字選單：另一個透明、滑鼠可穿透的視窗，平常隱藏。"""
        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-transparentcolor", _TRANSPARENT)
        win.configure(bg=_TRANSPARENT)
        cw, ch = menu_canvas_size()
        canvas = tk.Canvas(win, width=cw, height=ch, bg=_TRANSPARENT, highlightthickness=0)
        canvas.pack()
        self._menu_items = {}
        for d, (x1, y1, x2, y2) in menu_boxes().items():
            if d == "center":
                dot = canvas.create_oval((x1 + x2) / 2 - 6, (y1 + y2) / 2 - 6, (x1 + x2) / 2 + 6, (y1 + y2) / 2 + 6,
                                         fill=COLORS["windows"], outline="#202020")
                self._menu_items[d] = (dot, None)
                continue
            rect = canvas.create_rectangle(x1, y1, x2, y2, fill=_MENU_BG, outline=COLORS["windows"], width=2)
            text = canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=MENU_LABELS[d], fill="#ffffff",
                                      font=("Microsoft JhengHei UI", 11, "bold"))
            self._menu_items[d] = (rect, text)
        win.update_idletasks()
        self._make_click_through(win)
        win.withdraw()
        self._menu_win, self._menu_canvas = win, canvas
        self._menu_shown = False
        self._menu_choice: Optional[str] = None

    def update(self, status: str, cursor_pos: Optional[Tuple[int, int]], t: float, menu: Optional[str] = None) -> None:
        """menu：menu_state() 的結果，None = 不顯示三指選單。"""
        if not self.enabled or self._root is None:
            return
        try:
            self._update_menu(menu, cursor_pos)
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

    def _update_menu(self, menu: Optional[str], cursor_pos: Optional[Tuple[int, int]]) -> None:
        if menu is None or cursor_pos is None:
            if self._menu_shown:
                self._menu_win.withdraw()
                self._menu_shown = False
            return
        if not self._menu_shown:
            # 選單出現時固定在游標位置（三指時游標不會動）
            cw, ch = menu_canvas_size()
            x, y = cursor_pos
            self._menu_win.geometry(f"+{int(x - cw / 2)}+{int(y - ch / 2)}")
            self._menu_win.deiconify()
            self._menu_shown = True
            self._menu_choice = "?"   # 強制重畫
        if menu != self._menu_choice:
            for d in MENU_DIRS:
                rect, _ = self._menu_items[d]
                on = d == menu
                self._menu_canvas.itemconfigure(rect, fill=COLORS["windows"] if on else _MENU_BG)
            self._menu_choice = menu

    def close(self) -> None:
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
        self._root = None
        self.enabled = False
