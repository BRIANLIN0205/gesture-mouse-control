"""主程式：鏡頭 → 手部偵測 → 手勢判斷 → 滑鼠指令。

執行：python -m gesture_mouse [--config config.yaml] [--no-preview] [--tutorial] [--skip-tutorial]
預覽視窗按 q 或 Esc 結束；沒有預覽視窗時按 Ctrl+C 結束。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .config import Config, load_config
from .controller import Controller
from .gestures import Gesture, GestureClassifier
from .hand import CONNECTIONS

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"

GESTURE_LABELS = {
    Gesture.NONE: "-",
    Gesture.PALM: "PALM (MOVE)",
    Gesture.POINT: "POINT",
    Gesture.PINCH_INDEX: "PINCH INDEX",
    Gesture.PINCH_MIDDLE: "PINCH MIDDLE",
    Gesture.TWO_FINGER: "TWO FINGER",
    Gesture.FIST: "FIST (LIFT / HOLD = PAUSE)",
}


def _open_camera(cfg: Config):
    import cv2

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(cfg.camera.index, backend)
    if not cap.isOpened():
        cap = cv2.VideoCapture(cfg.camera.index)
    if not cap.isOpened():
        raise RuntimeError(f"打不開鏡頭（index={cfg.camera.index}），請檢查鏡頭是否被其他程式占用，或改 config.yaml 的 camera.index")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera.height)
    return cap


def _draw(frame, lm, gesture: Gesture, paused: bool, fps: float, margin) -> None:
    import cv2

    h, w = frame.shape[:2]
    # 有效區域框（絕對模式才有：手在框內就能碰到整個螢幕）
    if margin is not None:
        cv2.rectangle(frame, (int(w * margin), int(h * margin)), (int(w * (1 - margin)), int(h * (1 - margin))), (255, 200, 0), 1)
    if lm is not None:
        pts = [(int(p[0] * w), int(p[1] * h)) for p in lm]
        for a, b in CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], (0, 255, 0), 2)
        for p in pts:
            cv2.circle(frame, p, 3, (0, 0, 255), -1)
    status = "PAUSED" if paused else GESTURE_LABELS[gesture]
    color = (0, 0, 255) if paused else (0, 255, 0)
    cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    cv2.putText(frame, f"{fps:.0f} FPS", (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)


def run(cfg: Config, tutorial: str = "auto") -> None:
    """tutorial：auto = 第一次啟動才進教學；only = 只跑教學；off = 不進教學。"""
    import cv2

    from .detector import HandDetector
    from .hand import near_edge
    from .mouse import PynputMouse, enable_dpi_awareness, get_screen_size
    from .overlay import CursorOverlay, overlay_status
    from .sounds import SoundPlayer
    from .tutorial import TutorialPanel, TutorialTracker, mark_done, should_auto_run

    enable_dpi_awareness()
    screen = get_screen_size()
    print(f"螢幕解析度：{screen[0]}x{screen[1]}")

    detector = HandDetector(cfg.detection.min_detection_confidence, cfg.detection.min_tracking_confidence)
    classifier = GestureClassifier(cfg.detection.pinch_enter, cfg.detection.pinch_exit, cfg.detection.extend_ratio)
    controller = Controller(cfg, screen)
    mouse = PynputMouse()
    sounds = SoundPlayer(cfg.sound)
    overlay = CursorOverlay(cfg.overlay)
    cap = _open_camera(cfg)

    in_tutorial = tutorial == "only" or (tutorial == "auto" and should_auto_run())
    tracker = TutorialTracker() if in_tutorial else None
    panel = TutorialPanel() if in_tutorial else None
    tutorial_done_at = None
    if in_tutorial:
        print("進入手勢教學：照畫面右邊的步驟做，練習時不會真的操作滑鼠。按 s 跳過。")
    else:
        print("開始控制。張開手掌移動游標，短握拳可把手移回中間，握拳 1.5 秒暫停 / 恢復。",
              "預覽視窗按 q 或 Esc 結束。" if cfg.show_preview else "按 Ctrl+C 結束。")

    window_open = False
    start = time.monotonic()
    last = start
    fps = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("讀不到鏡頭畫面，結束。")
                break
            if cfg.camera.mirror:
                frame = cv2.flip(frame, 1)

            now = time.monotonic()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            lm = detector.detect(rgb, int((now - start) * 1000))
            h, w = frame.shape[:2]
            gesture = classifier.classify(lm, aspect=w / h)
            cmds = controller.update(gesture, lm, now)
            if tracker is None:
                mouse.execute(cmds)        # 教學模式不真的操作滑鼠
            sounds.execute(cmds)

            edge = lm is not None and near_edge(lm, cfg.detection.edge_margin)
            status = overlay_status(controller, lm is not None, edge)
            overlay.update(status, mouse.position if overlay.enabled else None, now)

            # 教學進度
            if tracker is not None:
                tracker.feed(cmds, controller.active, controller.paused)
                if tracker.done and tutorial_done_at is None:
                    tutorial_done_at = now
                    mark_done()
                if tutorial_done_at is not None and now - tutorial_done_at > 3:
                    if tutorial == "only":
                        break
                    tracker = None
                    controller = Controller(cfg, screen)   # 重新開始，清掉練習時的狀態
                    print("教學完成，開始控制。")

            dt = now - last
            last = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1 / dt) if fps else 1 / dt

            if window_open and not cfg.show_preview and tracker is None:
                cv2.destroyWindow("Gesture Mouse")   # 教學結束且設定不顯示預覽
                window_open = False
            if cfg.show_preview or tracker is not None:
                window_open = True
                _draw(frame, lm, controller.active, controller.paused, fps,
                      cfg.cursor.frame_margin if cfg.cursor.mode == "absolute" else None)
                if edge:
                    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), (0, 212, 255), 6)
                if tracker is not None:
                    frame = panel.render(frame, tracker, flash=int(now * 2) % 2 == 0)
                cv2.imshow("Gesture Mouse", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("s") and tracker is not None:
                    mark_done()
                    if tutorial == "only":
                        break
                    tracker = None
                    controller = Controller(cfg, screen)
                    print("已跳過教學，開始控制。")
    except KeyboardInterrupt:
        pass
    finally:
        mouse.execute(controller.release_all())
        overlay.close()
        cap.release()
        detector.close()
        cv2.destroyAllWindows()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="用鏡頭手勢控制滑鼠")
    parser.add_argument("--config", type=Path, default=None, help="設定檔路徑（預設為專案根目錄的 config.yaml）")
    parser.add_argument("--no-preview", action="store_true", help="不顯示鏡頭預覽視窗")
    parser.add_argument("--tutorial", action="store_true", help="只進行手勢教學（練習時不會操作滑鼠）")
    parser.add_argument("--skip-tutorial", action="store_true", help="第一次啟動也不進教學")
    args = parser.parse_args(argv)

    path = args.config or (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None)
    cfg = load_config(path)
    if args.no_preview:
        cfg.show_preview = False
    mode = "only" if args.tutorial else ("off" if args.skip_tutorial else "auto")
    run(cfg, tutorial=mode)
