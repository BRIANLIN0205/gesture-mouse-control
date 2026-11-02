from gesture_mouse.config import config_from_dict
from gesture_mouse.controller import Controller
from gesture_mouse.gestures import Gesture
from gesture_mouse.hand import near_edge
from gesture_mouse.overlay import COLORS, is_visible, overlay_status
from tests.handgen import make_hand

DT = 1 / 30


def ctrl_with(**control):
    cfg = config_from_dict({"control": {"stable_frames": 1, **control}})
    return Controller(cfg, (1920, 1080))


def feed(ctrl, gesture, lm, n=1, t0=0.0):
    t = t0
    for _ in range(n):
        ctrl.update(gesture, lm, t)
        t += DT
    return t


def test_status_for_each_gesture():
    hand = make_hand()
    c = ctrl_with()
    feed(c, Gesture.PALM, hand)
    assert overlay_status(c, True, False) == "move"
    feed(c, Gesture.PINCH_INDEX, hand, t0=0.1)
    assert overlay_status(c, True, False) == "pinch"
    feed(c, Gesture.TWO_FINGER, hand, t0=0.2)
    assert overlay_status(c, True, False) == "idle"    # 雙指預設沒有作用
    feed(c, Gesture.THREE_FINGER, hand, t0=0.25)
    assert overlay_status(c, True, False) == "windows"
    feed(c, Gesture.FIST, hand, t0=0.3)
    assert overlay_status(c, True, False) == "lift"
    feed(c, Gesture.POINT, hand, t0=0.4)
    assert overlay_status(c, True, False) == "idle"


def test_status_drag():
    c = ctrl_with(click_lock_seconds=0, drag_threshold_px=5)
    c.cfg.cursor.smoothing_min_cutoff = 1000
    c.filter.fx.min_cutoff = c.filter.fy.min_cutoff = 1000
    feed(c, Gesture.PALM, make_hand())
    for i in range(6):
        c.update(Gesture.PINCH_INDEX, make_hand(offset=(0.01 * i, 0)), 0.1 + i * DT)
    assert c.smart_state == "drag"
    assert overlay_status(c, True, False) == "drag"


def test_paused_wins_and_edge_warning():
    c = ctrl_with(pause_hold_seconds=0.1)
    feed(c, Gesture.PALM, make_hand())
    assert overlay_status(c, True, True) == "warning"
    assert overlay_status(c, False, False) == "nohand"
    feed(c, Gesture.FIST, make_hand(index=False), n=10, t0=1)
    assert c.paused
    assert overlay_status(c, True, True) == "paused"


def test_warning_blinks():
    assert is_visible("move", 0.3) and is_visible("move", 0.6)
    assert is_visible("warning", 0.1) != is_visible("warning", 0.3)


def test_every_status_has_color():
    for s in ["move", "pinch", "drag", "scroll", "lift", "paused", "nohand", "idle", "warning", "windows"]:
        assert s in COLORS


def test_near_edge():
    assert not near_edge(make_hand())
    assert near_edge(make_hand(offset=(0.49, 0)))      # 手移到最右邊
    assert near_edge(make_hand(offset=(0, 0.19)))      # 手腕快到畫面底部
