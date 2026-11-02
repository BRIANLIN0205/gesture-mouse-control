from gesture_mouse.app import GESTURE_LABELS
from gesture_mouse.gestures import Gesture


def test_every_gesture_has_preview_label():
    # 少一個標籤會讓預覽視窗在比出該手勢時當機
    for g in Gesture:
        assert g in GESTURE_LABELS
