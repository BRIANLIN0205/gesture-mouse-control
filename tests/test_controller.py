from gesture_mouse.config import Config, config_from_dict
from gesture_mouse.controller import Click, Controller, MoveBy, MoveTo, Press, Release, Scroll
from gesture_mouse.gestures import Gesture
from tests.handgen import make_hand

SCREEN = (1920, 1080)
DT = 1 / 30


def run(ctrl, frames, t0=0.0):
    """frames: [(gesture, landmarks)]，回傳每一幀的指令清單。"""
    out = []
    t = t0
    for g, lm in frames:
        out.append(ctrl.update(g, lm, t))
        t += DT
    return out


def flat(outs):
    return [c for cmds in outs for c in cmds]


def kinds(outs):
    return [type(c).__name__ for c in flat(outs)]


def make_ctrl(mode="absolute", cursor=None, **control):
    cfg = config_from_dict({"control": control, "cursor": {"mode": mode, **(cursor or {})}})
    return Controller(cfg, SCREEN)


def test_move_emits_moveto_after_debounce():
    ctrl = make_ctrl()
    hand = make_hand()
    outs = run(ctrl, [(Gesture.PALM, hand)] * 3)
    assert outs[0] == []                     # 第一幀還在確認
    assert isinstance(outs[1][0], MoveTo)
    assert isinstance(outs[2][0], MoveTo)


def test_single_frame_glitch_is_ignored():
    ctrl = make_ctrl()
    hand = make_hand()
    run(ctrl, [(Gesture.PALM, hand)] * 3)
    outs = run(ctrl, [(Gesture.PINCH_INDEX, hand), (Gesture.PALM, hand)])
    assert "Press" not in kinds(outs)


def test_pinch_index_press_drag_release():
    ctrl = make_ctrl(stable_frames=1)
    hand = make_hand()
    outs = run(ctrl, [(Gesture.PALM, hand), (Gesture.PINCH_INDEX, hand), (Gesture.PINCH_INDEX, hand), (Gesture.PALM, hand)])
    assert outs[1][0] == Press("left")
    assert isinstance(outs[1][1], MoveTo)       # 按住時繼續移動 = 拖曳
    assert isinstance(outs[2][0], MoveTo)
    assert outs[3][0] == Release("left")


def test_pinch_middle_right_click_once():
    ctrl = make_ctrl(stable_frames=1)
    hand = make_hand()
    outs = run(ctrl, [(Gesture.PINCH_MIDDLE, hand)] * 5)
    assert flat(outs) == [Click("right")]


def test_lost_hand_releases_button():
    ctrl = make_ctrl(stable_frames=1)
    hand = make_hand()
    outs = run(ctrl, [(Gesture.PINCH_INDEX, hand), (Gesture.NONE, None)])
    assert outs[0][0] == Press("left")
    assert outs[1] == [Release("left")]


def test_release_all():
    ctrl = make_ctrl(stable_frames=1)
    run(ctrl, [(Gesture.PINCH_INDEX, make_hand())])
    assert ctrl.release_all() == [Release("left")]
    assert ctrl.release_all() == []


def test_scroll_up_when_hand_moves_up():
    ctrl = make_ctrl(stable_frames=1, scroll_sensitivity=100)
    frames = [(Gesture.TWO_FINGER, make_hand(index=True, middle=True, offset=(0, -0.02 * i))) for i in range(5)]
    cmds = flat(run(ctrl, frames))
    assert cmds and all(isinstance(c, Scroll) for c in cmds)
    assert sum(c.steps for c in cmds) == 8      # 0.08 × 100


def test_scroll_down_and_invert():
    frames = [(Gesture.TWO_FINGER, make_hand(index=True, middle=True, offset=(0, 0.02 * i))) for i in range(5)]
    down = flat(run(make_ctrl(stable_frames=1, scroll_sensitivity=100), frames))
    assert sum(c.steps for c in down) == -8
    inv = flat(run(make_ctrl(stable_frames=1, scroll_sensitivity=100, scroll_invert=True), frames))
    assert sum(c.steps for c in inv) == 8


def test_fist_hold_toggles_pause():
    ctrl = make_ctrl(stable_frames=1, pause_hold_seconds=0.5)
    fist = make_hand(index=False)
    run(ctrl, [(Gesture.FIST, fist)] * 10)       # 0.3 秒，不夠
    assert not ctrl.paused
    run(ctrl, [(Gesture.FIST, fist)] * 10, t0=0.4)
    assert ctrl.paused

    # 暫停中：移動與點擊都沒反應
    hand = make_hand()
    outs = run(ctrl, [(Gesture.PALM, hand), (Gesture.PINCH_INDEX, hand), (Gesture.PINCH_MIDDLE, hand)], t0=2)
    assert flat(outs) == []

    # 再握拳一次恢復
    run(ctrl, [(Gesture.FIST, fist)] * 30, t0=3)
    assert not ctrl.paused
    outs = run(ctrl, [(Gesture.PALM, hand)], t0=5)
    assert isinstance(outs[0][0], MoveTo)


def test_fist_held_long_toggles_only_once():
    ctrl = make_ctrl(stable_frames=1, pause_hold_seconds=0.2)
    run(ctrl, [(Gesture.FIST, make_hand(index=False))] * 90)  # 3 秒
    assert ctrl.paused


def test_cursor_mapping_corners_and_clamp():
    ctrl = make_ctrl()
    m = ctrl.cfg.cursor.frame_margin
    assert ctrl.to_screen((m, m)) == (0, 0)
    assert ctrl.to_screen((1 - m, 1 - m)) == (SCREEN[0] - 1, SCREEN[1] - 1)
    assert ctrl.to_screen((0.0, 1.0)) == (0, SCREEN[1] - 1)       # 超出範圍會被夾住
    x, y = ctrl.to_screen((0.5, 0.5))
    assert abs(x - (SCREEN[0] - 1) / 2) < 1e-6 and abs(y - (SCREEN[1] - 1) / 2) < 1e-6


def test_custom_gesture_mapping():
    cfg = config_from_dict({"control": {"stable_frames": 1}, "gestures": {"pinch_middle": "double_click", "pinch_index": "click_left"}})
    ctrl = Controller(cfg, SCREEN)
    hand = make_hand()
    assert run(ctrl, [(Gesture.PINCH_MIDDLE, hand)])[0] == [Click("left", 2)]
    outs = run(ctrl, [(Gesture.PINCH_INDEX, hand)] * 3)
    assert flat(outs) == [Click("left")]


# ---------- 相對移動 ----------

def moving_hand(i, step=0.01, dy=0.0):
    return make_hand(offset=(step * i, dy * i))


def test_default_mode_is_relative():
    assert Config().cursor.mode == "relative"


def test_relative_first_frame_does_not_jump():
    ctrl = make_ctrl("relative", stable_frames=1)
    outs = run(ctrl, [(Gesture.PALM, make_hand(offset=(0.3, 0.1)))])
    assert outs[0] == []                     # 第一幀只記錄位置，不移動


def test_relative_moves_in_hand_direction():
    ctrl = make_ctrl("relative", cursor={"smoothing_min_cutoff": 1000}, stable_frames=1)
    cmds = flat(run(ctrl, [(Gesture.PALM, moving_hand(i, 0.01, -0.005)) for i in range(10)]))
    assert cmds and all(isinstance(c, MoveBy) for c in cmds)
    assert sum(c.dx for c in cmds) > 0      # 手往右 → 游標往右
    assert sum(c.dy for c in cmds) < 0      # 手往上 → 游標往上


def test_relative_still_hand_does_not_drift():
    ctrl = make_ctrl("relative", stable_frames=1)
    assert flat(run(ctrl, [(Gesture.PALM, make_hand())] * 30)) == []


def test_relative_acceleration():
    """同樣的總位移，快速移動時游標走得比慢速遠。"""
    cur = {"smoothing_min_cutoff": 1000, "relative_accel": 2.0}
    slow = make_ctrl("relative", cursor=cur, stable_frames=1)
    fast = make_ctrl("relative", cursor=cur, stable_frames=1)
    slow_dx = sum(c.dx for c in flat(run(slow, [(Gesture.PALM, moving_hand(i, 0.002)) for i in range(51)])))
    fast_dx = sum(c.dx for c in flat(run(fast, [(Gesture.PALM, moving_hand(i, 0.02)) for i in range(6)])))
    # 總位移都是 0.1 個鏡頭寬
    assert fast_dx > slow_dx * 1.5


def test_relative_no_accel_is_linear():
    cur = {"smoothing_min_cutoff": 1000, "relative_accel": 0.0, "relative_gain": 1.0}
    ctrl = make_ctrl("relative", cursor=cur, stable_frames=1)
    dx = sum(c.dx for c in flat(run(ctrl, [(Gesture.PALM, moving_hand(i, 0.01)) for i in range(11)])))
    assert abs(dx - 0.1 * SCREEN[0]) <= 2


def test_relative_reentry_does_not_jump():
    """移動 → 張開手掌（停住）→ 手移到別處再移動：游標不應跳過去。"""
    cur = {"smoothing_min_cutoff": 1000}
    ctrl = make_ctrl("relative", cursor=cur, stable_frames=1)
    run(ctrl, [(Gesture.PALM, make_hand())] * 3)
    run(ctrl, [(Gesture.NONE, make_hand(offset=(-0.3, 0)))] * 3)
    outs = run(ctrl, [(Gesture.PALM, make_hand(offset=(-0.3, 0)))] * 2)
    assert flat(outs) == []


def test_relative_drag_keeps_moving():
    cur = {"smoothing_min_cutoff": 1000}
    ctrl = make_ctrl("relative", cursor=cur, stable_frames=1)
    frames = [(Gesture.PALM, moving_hand(i)) for i in range(3)] + [(Gesture.PINCH_INDEX, moving_hand(i)) for i in range(3, 6)]
    cmds = flat(run(ctrl, frames))
    i = cmds.index(Press("left"))
    assert any(isinstance(c, MoveBy) for c in cmds[i + 1:])


def test_short_fist_lifts_cursor():
    """預設：手掌移動 → 短握拳（抬起）移回中間 → 再張開手掌：游標不跳回去，也沒有暫停。"""
    cur = {"smoothing_min_cutoff": 1000}
    ctrl = make_ctrl("relative", cursor=cur, stable_frames=1)
    moved = flat(run(ctrl, [(Gesture.PALM, moving_hand(i, 0.02)) for i in range(5)]))
    assert sum(c.dx for c in moved) > 0
    lifted = flat(run(ctrl, [(Gesture.FIST, moving_hand(i, -0.02)) for i in range(5, 10)], t0=1))
    assert lifted == []
    outs = run(ctrl, [(Gesture.PALM, make_hand(offset=(-0.1, 0)))] * 2, t0=2)
    assert flat(outs) == []
    assert not ctrl.paused


def test_point_does_nothing_by_default():
    ctrl = make_ctrl("relative", stable_frames=1)
    assert flat(run(ctrl, [(Gesture.POINT, moving_hand(i, 0.02)) for i in range(10)])) == []


def test_default_pause_hold_is_long():
    assert Config().control.pause_hold_seconds == 1.5
