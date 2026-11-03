"""Windows 右下角系統匣的手勢滑鼠圖示。

右鍵（或左鍵）點圖示會出現選單：開啟設定、暫停 / 恢復、結束。
圖示顏色：綠 = 控制中、紅 = 暫停。需要 PySide6，沒裝的話只是沒有圖示，不影響控制。

手勢程式的主迴圈每幀呼叫 poll()，讓 Qt 處理滑鼠點擊並回傳使用者選了什麼。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def _make_icon(color: str):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(QPen(QColor("#202020"), 3))
    p.drawEllipse(4, 4, 56, 56)
    # 簡單的手掌：四根指頭 + 掌心
    p.setBrush(QColor("white"))
    p.setPen(Qt.NoPen)
    for i, h in enumerate((16, 20, 19, 15)):
        p.drawRoundedRect(17 + i * 8, 36 - h, 6, h + 4, 3, 3)
    p.drawRoundedRect(17, 32, 30, 16, 6, 6)
    p.drawRoundedRect(10, 30, 9, 6, 3, 3)
    p.end()
    return QIcon(pix)


class TrayIcon:
    def __init__(self, config_path: Optional[Path]) -> None:
        self.config_path = config_path
        self.enabled = False
        self._actions: List[str] = []
        self._settings_proc: Optional[subprocess.Popen] = None
        self._paused: Optional[bool] = None
        try:
            self._create()
            self.enabled = True
        except Exception as e:   # 沒裝 PySide6 或系統不支援：沒有圖示，但手勢控制照常
            print(f"無法建立系統匣圖示（設定介面需要 PySide6）：{e}")

    def _create(self) -> None:
        from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

        if not QSystemTrayIcon.isSystemTrayAvailable():
            raise RuntimeError("這台電腦沒有系統匣")
        self._app = QApplication.instance() or QApplication(sys.argv[:1])
        self._app.setQuitOnLastWindowClosed(False)
        self._icons = {False: _make_icon("#2ecc40"), True: _make_icon("#e8262e")}

        menu = QMenu()
        menu.addAction("開啟設定").triggered.connect(lambda: self._actions.append("settings"))
        self._pause_action = menu.addAction("暫停")
        self._pause_action.triggered.connect(lambda: self._actions.append("toggle_pause"))
        menu.addSeparator()
        menu.addAction("結束手勢滑鼠").triggered.connect(lambda: self._actions.append("quit"))
        self._menu = menu

        tray = QSystemTrayIcon(self._icons[False])
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_activated)
        tray.setToolTip("手勢滑鼠：控制中")
        tray.show()
        self._tray = tray

    def _on_activated(self, reason) -> None:
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason == QSystemTrayIcon.DoubleClick:
            self._actions.append("settings")
        elif reason == QSystemTrayIcon.Trigger:   # 左鍵單擊也跳出選單
            self._menu.popup(QCursor.pos())

    def set_paused(self, paused: bool) -> None:
        if not self.enabled or paused == self._paused:
            return
        self._paused = paused
        self._tray.setIcon(self._icons[paused])
        self._tray.setToolTip("手勢滑鼠：暫停中" if paused else "手勢滑鼠：控制中")
        self._pause_action.setText("恢復" if paused else "暫停")

    def poll(self) -> List[str]:
        """處理圖示的點擊，回傳使用者選的動作：settings / toggle_pause / quit。"""
        if not self.enabled:
            return []
        try:
            self._app.processEvents()
        except Exception as e:
            print(f"系統匣圖示發生錯誤，已關閉：{e}")
            self.close()
            return []
        actions, self._actions = self._actions, []
        if "settings" in actions:
            self.open_settings()
        return [a for a in actions if a != "settings"]

    def open_settings(self) -> None:
        """開設定視窗（獨立程式，避免卡住鏡頭畫面）。已經開著就不再開第二個。"""
        if self._settings_proc is not None and self._settings_proc.poll() is None:
            return
        cmd = [sys.executable, "-m", "gesture_mouse.settings_gui"]
        if self.config_path:
            cmd += ["--config", str(self.config_path)]
        try:
            self._settings_proc = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parent.parent))
        except Exception as e:
            print(f"無法開啟設定視窗：{e}")

    def close(self) -> None:
        if self.enabled:
            try:
                self._tray.hide()
            except Exception:
                pass
        self.enabled = False
