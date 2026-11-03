"""手勢程式執行中自動重新讀取 config.yaml（設定介面改了數值就馬上生效）。"""

from __future__ import annotations

import time
from dataclasses import fields
from pathlib import Path
from typing import Optional, Set, Tuple

from .config import Config, load_config

SECTIONS = ("camera", "detection", "cursor", "control", "sound", "overlay", "two_hands")

# 這些欄位在程式啟動時就用掉了，改了要重開手勢程式才會生效
RESTART_KEYS = {
    "camera.index", "camera.width", "camera.height", "camera.mirror",
    "detection.min_detection_confidence", "detection.min_tracking_confidence", "detection.swap_hands",
}


def diff_config(old: Config, new: Config) -> Set[str]:
    """回傳有變動的欄位，格式為「區塊.欄位」。"""
    changed = set()
    for sec in SECTIONS:
        a, b = getattr(old, sec), getattr(new, sec)
        for f in fields(a):
            if getattr(a, f.name) != getattr(b, f.name):
                changed.add(f"{sec}.{f.name}")
    for g in set(old.gestures) | set(new.gestures):
        if old.gestures.get(g) != new.gestures.get(g):
            changed.add(f"gestures.{g}")
    if old.show_preview != new.show_preview:
        changed.add("show_preview")
    return changed


def apply_config(target: Config, new: Config) -> Tuple[Set[str], Set[str]]:
    """把 new 的數值直接寫進 target（原地修改，持有 target 子物件的元件也會看到新值）。

    回傳 (有變動的欄位, 其中要重開才生效的欄位)。要重開的欄位不會套用，避免和實際狀態不一致。
    """
    changed = diff_config(target, new)
    restart = changed & RESTART_KEYS
    for key in changed - restart:
        if key == "show_preview":
            target.show_preview = new.show_preview
        elif key.startswith("gestures."):
            target.gestures.clear()
            target.gestures.update(new.gestures)
        else:
            sec, name = key.split(".", 1)
            setattr(getattr(target, sec), name, getattr(getattr(new, sec), name))
    return changed, restart


class ConfigWatcher:
    """每隔一段時間檢查設定檔修改時間，有變就重新讀取。"""

    def __init__(self, path: Optional[Path], interval: float = 0.5) -> None:
        self.path = Path(path) if path else None
        self.interval = interval
        self._next = 0.0
        self._mtime = self._stat()

    def _stat(self) -> Optional[float]:
        try:
            return self.path.stat().st_mtime if self.path else None
        except OSError:
            return None

    def poll(self, now: Optional[float] = None) -> Optional[Config]:
        """設定檔有改且讀得出來就回傳新設定，否則回傳 None。"""
        if self.path is None:
            return None
        now = time.monotonic() if now is None else now
        if now < self._next:
            return None
        self._next = now + self.interval
        mtime = self._stat()
        if mtime is None or mtime == self._mtime:
            return None
        self._mtime = mtime
        try:
            return load_config(self.path)
        except Exception as e:   # 存到一半或格式錯：維持原本的設定
            print(f"設定檔讀取失敗，沿用原本的設定：{e}")
            return None
