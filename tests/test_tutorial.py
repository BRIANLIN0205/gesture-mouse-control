import numpy as np

from gesture_mouse.config import config_from_dict
from gesture_mouse.controller import FLICK_NAV, FLICK_WINDOWS, Click, Controller, MoveBy, PauseChanged, Press, Release, Scroll
from gesture_mouse.gestures import Gesture
from gesture_mouse.tutorial import STEPS, TutorialPanel, TutorialTracker


def test_steps_complete_in_order():
    t = TutorialTracker()
    # 第一步：張開手掌移動 15 幀
    for _ in range(14):
        assert not t.feed([MoveBy(3, 0)], Gesture.PALM, False)
    # 還在第一步時點擊不算
    t.feed([Click("left")], Gesture.PINCH_INDEX, False)
    assert t.current.key == "move"
    assert t.feed([MoveBy(3, 0)], Gesture.PALM, False)
    assert t.current.key == "lift"

    t.feed([], Gesture.FIST, False)
    assert t.feed([], Gesture.PALM, False)
    assert t.feed([Click("left")], Gesture.PALM, False)                 # click
    assert not t.feed([Click("right")], Gesture.PINCH_MIDDLE, False)     # 要用食指捏住
    assert t.feed([Click("right")], Gesture.PINCH_INDEX, False)          # hold_right
    t.feed([Press("left"), MoveBy(30, 0)], Gesture.PINCH_INDEX, False)
    assert t.feed([Release("left")], Gesture.PALM, False)                # drag
    assert t.feed([Click("right")], Gesture.PINCH_MIDDLE, False)         # middle
    t.feed([Scroll(2)], Gesture.TWO_FINGER, False)
    assert t.feed([Scroll(-1)], Gesture.TWO_FINGER, False)               # scroll
    assert not t.feed([FLICK_WINDOWS["left"]], Gesture.THREE_FINGER, False)
    assert t.feed([FLICK_NAV["left"]], Gesture.TWO_FINGER, False)        # nav
    assert t.feed([FLICK_WINDOWS["down"]], Gesture.THREE_FINGER, False)  # windows
    assert t.feed([PauseChanged(True)], Gesture.FIST, True)              # pause
    assert not t.done
    assert t.feed([PauseChanged(False)], Gesture.FIST, False)            # resume
    assert t.done and t.current is None
    assert t.index == len(STEPS)


def test_lift_requires_no_pause():
    t = TutorialTracker()
    t.index = 1
    t.feed([], Gesture.FIST, False)
    assert not t.feed([], Gesture.PALM, True)


def test_default_pinch_actions_satisfy_tutorial():
    """用預設設定實際跑控制器，確認教學步驟真的做得到（輕捏、捏住右鍵、拖曳）。"""
    from tests.handgen import make_hand

    cfg = config_from_dict({"control": {"stable_frames": 1}, "cursor": {"smoothing_min_cutoff": 1000}})
    c = Controller(cfg, (1920, 1080))
    t = TutorialTracker()
    t.index = 2
    tt = [0.0]

    def step(g, lm):
        cmds = c.update(g, lm, tt[0])
        tt[0] += 1 / 30
        t.feed(cmds, c.active, c.paused)

    hand = make_hand()
    step(Gesture.PALM, hand)
    for _ in range(3):
        step(Gesture.PINCH_INDEX, hand)
    step(Gesture.PALM, hand)
    assert t.current.key == "hold_right"
    for _ in range(25):
        step(Gesture.PINCH_INDEX, hand)
    step(Gesture.PALM, hand)
    assert t.current.key == "drag"
    for i in range(20):
        step(Gesture.PINCH_INDEX, make_hand(offset=(0.01 * i, 0)))
    step(Gesture.PALM, make_hand(offset=(0.2, 0)))
    assert t.current.key == "middle"


def test_panel_renders_without_font():
    p = TutorialPanel()
    p.font = p.title_font = None
    out = p.render(np.zeros((480, 640, 3), dtype=np.uint8), TutorialTracker(), flash=True)
    assert out.shape == (480, 640 + TutorialPanel.WIDTH, 3)
