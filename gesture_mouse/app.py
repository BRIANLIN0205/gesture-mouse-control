"""主程式：鏡頭 → 手部偵測 → 手勢判斷 → 滑鼠指令。

執行：python -m gesture_mouse [--config config.yaml] [--no-preview]
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
    Gesture.MOVE: "MOVE",
    Gesture.PINCH_INDEX: "PINCH INDEX",
    Gesture.PINCH_MIDDLE: "PINCH MIDDLE",
    Gesture.TWO_FINGER: "TWO FINGER",
    Gesture.FIST: "FIST",
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


def _draw(frame, lm, gesture: Gesture, paused: bool, fps: float, margin: float) -> None:
    import cv2

    h, w = frame.shape[:2]
    # 有效區域框（手在框內就能碰到整個螢幕）
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


def run(cfg: Config) -> None:
    import cv2

    from .detector import HandDetector
    from .mouse import PynputMouse, enable_dpi_awareness, get_screen_size

    enable_dpi_awareness()
    screen = get_screen_size()
    print(f"螢幕解析度：{screen[0]}x{screen[1]}")

    detector = HandDetector(cfg.detection.min_detection_confidence, cfg.detection.min_tracking_confidence)
    classifier = GestureClassifier(cfg.detection.pinch_enter, cfg.detection.pinch_exit, cfg.detection.extend_ratio)
    controller = Controller(cfg, screen)
    mouse = PynputMouse()
    cap = _open_camera(cfg)

    print("開始控制。握拳維持約 1 秒可暫停 / 恢復。", "預覽視窗按 q 或 Esc 結束。" if cfg.show_preview else "按 Ctrl+C 結束。")
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
            mouse.execute(controller.update(gesture, lm, now))

            dt = now - last
            last = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1 / dt) if fps else 1 / dt

            if cfg.show_preview:
                _draw(frame, lm, controller.active, controller.paused, fps, cfg.cursor.frame_margin)
                cv2.imshow("Gesture Mouse", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        mouse.execute(controller.release_all())
        cap.release()
        detector.close()
        if cfg.show_preview:
            cv2.destroyAllWindows()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="用鏡頭手勢控制滑鼠")
    parser.add_argument("--config", type=Path, default=None, help="設定檔路徑（預設為專案根目錄的 config.yaml）")
    parser.add_argument("--no-preview", action="store_true", help="不顯示鏡頭預覽視窗")
    args = parser.parse_args(argv)

    path = args.config or (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None)
    cfg = load_config(path)
    if args.no_preview:
        cfg.show_preview = False
    run(cfg)
