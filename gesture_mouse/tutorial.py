"""手勢教學：依序請使用者做每個手勢，做對就打勾。

練習時不會真的操作滑鼠（點擊、拖曳、捲動都只是判斷），可以放心亂試。
第一次啟動會自動進入一次；之後可用 `python -m gesture_mouse --tutorial` 再練習。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .controller import ARROWS, FLICK_NAV, FLICK_WINDOWS, Click, Hotkey, MoveBy, MoveTo, PauseChanged, Press, Release, Scroll, Zoom
from .gestures import Gesture
from .two_hands import VOLUME_DOWN, VOLUME_UP

DONE_FLAG = Path(__file__).resolve().parent.parent / ".tutorial_done"


@dataclass
class Step:
    key: str
    zh: str
    en: str


STEPS: List[Step] = [
    Step("move", "張開手掌，左右上下移動（移動游標）", "Open palm and move around (move cursor)"),
    Step("lift", "短握拳再張開手掌（抬起，游標停住）", "Quick fist, then open palm (lift)"),
    Step("click", "食指和拇指輕捏一下（左鍵）", "Quick index pinch (left click)"),
    Step("hold_right", "食指和拇指捏住不動約 0.6 秒（右鍵）", "Index pinch and hold still (right click)"),
    Step("drag", "食指和拇指捏住並移動，再放開（拖曳）", "Index pinch and move, then release (drag)"),
    Step("scroll", "中指捏拇指，往上或下移（越遠捲越快）", "Middle pinch, move up/down (scroll)"),
    Step("arrow", "中指捏拇指，往上或下一點就放開（方向鍵）", "Middle pinch, nudge up/down, release (arrow)"),
    Step("nav", "中指捏拇指，往左或右移再放開（翻頁）", "Middle pinch, move left/right, release (back/fwd)"),
    Step("windows", "伸出食指、中指、無名指，往任一方向甩（視窗）", "Three fingers: flick any direction (windows)"),
    Step("zoom", "兩手都用食指捏拇指，拉開或靠近（縮放）", "Both hands index pinch, spread/close (zoom)"),
    Step("volume", "左手中指捏拇指，往上或下移（音量）", "Left hand middle pinch, move up/down (volume)"),
    Step("pause", "握拳約 1.5 秒（暫停，會有提示音）", "Hold fist ~1.5 s (pause)"),
    Step("resume", "再握拳約 1.5 秒（恢復）", "Hold fist again (resume)"),
]


class TutorialTracker:
    """看每一幀的指令與手勢，判斷目前這一步是否完成。步驟要依序完成。"""

    def __init__(self) -> None:
        self.index = 0
        self._move_frames = 0
        self._scroll_total = 0
        self._dragging = False
        self._saw_fist = False

    @property
    def done(self) -> bool:
        return self.index >= len(STEPS)

    @property
    def current(self) -> Optional[Step]:
        return None if self.done else STEPS[self.index]

    def _advance(self) -> None:
        self.index += 1
        self._move_frames = 0
        self._scroll_total = 0
        self._dragging = False
        self._saw_fist = False

    def feed(self, commands: Iterable[object], active: Gesture, paused: bool) -> bool:
        """回傳這一幀是否剛完成一步。"""
        step = self.current
        if step is None:
            return False
        cmds = list(commands)
        ok = False
        k = step.key
        if k == "move":
            if active == Gesture.PALM and any(isinstance(c, (MoveBy, MoveTo)) for c in cmds):
                self._move_frames += 1
            ok = self._move_frames >= 15
        elif k == "lift":
            if active == Gesture.FIST:
                self._saw_fist = True
            ok = self._saw_fist and active == Gesture.PALM and not paused
        elif k == "click":
            ok = Click("left") in cmds
        elif k == "hold_right":
            ok = Click("right") in cmds and active == Gesture.PINCH_INDEX
        elif k == "drag":
            if Press("left") in cmds:
                self._dragging = True
            ok = self._dragging and Release("left") in cmds
        elif k == "scroll":
            self._scroll_total += sum(abs(c.steps) for c in cmds if isinstance(c, Scroll))
            ok = self._scroll_total >= 3
        elif k == "arrow":
            ok = any(c in ARROWS.values() for c in cmds if isinstance(c, Hotkey))
        elif k == "nav":
            ok = any(c in FLICK_NAV.values() for c in cmds if isinstance(c, Hotkey))
        elif k == "windows":
            ok = any(c in FLICK_WINDOWS.values() for c in cmds if isinstance(c, Hotkey))
        elif k == "zoom":
            ok = any(isinstance(c, Zoom) for c in cmds)
        elif k == "volume":
            ok = VOLUME_UP in cmds or VOLUME_DOWN in cmds
        elif k == "pause":
            ok = PauseChanged(True) in cmds
        elif k == "resume":
            ok = PauseChanged(False) in cmds
        if ok:
            self._advance()
        return ok


def should_auto_run() -> bool:
    return not DONE_FLAG.exists()


def mark_done() -> None:
    try:
        DONE_FLAG.write_text("ok\n", encoding="utf-8")
    except OSError:
        pass


# ---------- 畫面 ----------

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msjh.ttc",      # 微軟正黑體
    "C:/Windows/Fonts/msjhl.ttc",
    "C:/Windows/Fonts/mingliu.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _load_font(size: int):
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None


class TutorialPanel:
    """在預覽畫面右邊畫一塊步驟清單。有中文字型就顯示中文，否則顯示英文。"""

    WIDTH = 420

    def __init__(self) -> None:
        self.font = _load_font(20)
        self.title_font = _load_font(24)

    def render(self, frame, tracker: TutorialTracker, flash: bool):
        import numpy as np

        h = frame.shape[0]
        panel = np.full((h, self.WIDTH, 3), 32, dtype=np.uint8)
        lines = []
        if tracker.done:
            title = ("教學完成！3 秒後開始控制", "Done! Starting in 3 s")
        else:
            title = ("手勢教學（按 s 跳過）", "Tutorial (press s to skip)")
        lines.append((title, (255, 255, 255), True))
        for i, step in enumerate(STEPS):
            if i < tracker.index:
                color, mark = (90, 200, 90), "√ " if self.font else "[x] "
            elif i == tracker.index:
                color, mark = ((255, 220, 0) if flash else (255, 255, 255)), "→ " if self.font else "> "
            else:
                color, mark = (140, 140, 140), "   " if self.font else "[ ] "
            lines.append(((mark + step.zh, mark + step.en), color, False))

        if self.font is not None:
            from PIL import Image, ImageDraw

            img = Image.fromarray(panel)
            draw = ImageDraw.Draw(img)
            y = 16
            for (zh, _), color, is_title in lines:
                font = self.title_font if is_title else self.font
                draw.text((14, y), zh, font=font, fill=color)
                y += 44 if is_title else 34
            panel = np.array(img)[:, :, ::-1].copy()   # RGB → BGR
        else:
            import cv2

            y = 30
            for (_, en), color, is_title in lines:
                cv2.putText(panel, en, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5 if not is_title else 0.6,
                            color[::-1], 1, cv2.LINE_AA)
                y += 34 if is_title else 28
        return np.hstack([frame, panel])
