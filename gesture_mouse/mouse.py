"""用 pynput 執行滑鼠指令。"""

from __future__ import annotations

import sys
from typing import Iterable, Tuple

from .controller import Click, MoveBy, MoveTo, Press, Release, Scroll


def enable_dpi_awareness() -> None:
    """Windows 開啟縮放（例如 125%、150%）時，讓座標對應實際像素，游標才不會偏移。"""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def get_screen_size() -> Tuple[int, int]:
    """主螢幕解析度。"""
    if sys.platform == "win32":
        import ctypes

        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        size = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        return size
    except Exception:
        return 1920, 1080


class PynputMouse:
    def __init__(self) -> None:
        from pynput.mouse import Button, Controller

        self._mouse = Controller()
        self._buttons = {"left": Button.left, "right": Button.right}

    @property
    def position(self) -> Tuple[int, int]:
        x, y = self._mouse.position
        return int(x), int(y)

    def execute(self, commands: Iterable[object]) -> None:
        for cmd in commands:
            if isinstance(cmd, MoveTo):
                self._mouse.position = (cmd.x, cmd.y)
            elif isinstance(cmd, MoveBy):
                self._mouse.move(cmd.dx, cmd.dy)
            elif isinstance(cmd, Press):
                self._mouse.press(self._buttons[cmd.button])
            elif isinstance(cmd, Release):
                self._mouse.release(self._buttons[cmd.button])
            elif isinstance(cmd, Click):
                self._mouse.click(self._buttons[cmd.button], cmd.count)
            elif isinstance(cmd, Scroll):
                self._mouse.scroll(0, cmd.steps)
