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


def make_ctrl(mode="absolute", cursor=None, gestures=None, **control):
    cfg = config_from_dict({"control": control, "cursor": {"mode": mode, **(cursor or {})}, "gestures": gestures or {}})
    return Controller(cfg, SCREEN)


def test_move_emits_moveto_after_debounce():
    ctrl = make_ctrl()
    hand = make_hand()
    outs = run(ctrl, [(Gesture.PALM, hand)] * 3)
    assert outs[0] == []                     # 第一幀還在確認
    assert isinstance(outs[1][0], MoveTo)
    assert isinstance(outs[2][0], MoveTo)


def test_single_frame_glitch_is_ignored():
    ctrl = make_ctrl(gestures={"pinch_index": "hold_left"})
    hand = make_hand()
    run(ctrl, [(Gesture.PALM, hand)] * 3)
    outs = run(ctrl, [(Gesture.PINCH_INDEX, hand), (Gesture.PALM, hand)])
    assert "Press" not in kinds(outs)


def test_pinch_index_press_drag_release():
    ctrl = make_ctrl(gestures={"pinch_index": "hold_left"}, stable_frames=1, click_lock_seconds=0)
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
    ctrl = make_ctrl(gestures={"pinch_index": "hold_left"}, stable_frames=1)
    hand = make_hand()
    outs = run(ctrl, [(Gesture.PINCH_INDEX, hand), (Gesture.NONE, None)])
    assert outs[0][0] == Press("left")
    assert outs[1] == [Release("left")]


def test_release_all():
    ctrl = make_ctrl(gestures={"pinch_index": "hold_left"}, stable_frames=1)
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
    ctrl = make_ctrl("relative", gestures={"pinch_index": "hold_left"}, cursor=cur, stable_frames=1, click_lock_seconds=0.05)
    frames = [(Gesture.PALM, moving_hand(i)) for i in range(3)] + [(Gesture.PINCH_INDEX, moving_hand(i)) for i in range(3, 9)]
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


# ---------- 捏合瞬間鎖住游標 ----------

def test_cursor_locked_right_after_pinch():
    cur = {"smoothing_min_cutoff": 1000}
    ctrl = make_ctrl("relative", gestures={"pinch_index": "hold_left"}, cursor=cur, stable_frames=1, click_lock_seconds=0.15)
    run(ctrl, [(Gesture.PALM, moving_hand(i)) for i in range(3)])
    # 捏合後 0.1 秒內手還在動：只有 Press，沒有移動
    outs = run(ctrl, [(Gesture.PINCH_INDEX, moving_hand(i)) for i in range(3, 6)], t0=3 * DT)
    cmds = flat(outs)
    assert cmds == [Press("left")]
    # 超過鎖定時間後繼續移動 = 拖曳，而且不會把鎖定期間的位移一次補上（不跳）
    later = flat(run(ctrl, [(Gesture.PINCH_INDEX, moving_hand(i)) for i in range(6, 10)], t0=6 * DT + 0.1))
    moves = [c for c in later if isinstance(c, MoveBy)]
    assert moves and max(abs(m.dx) for m in moves) < 0.05 * SCREEN[0]


def test_cursor_frozen_while_pinch_is_being_confirmed():
    """手勢正從移動切到捏合（還在確認中）那一幀，游標不動。"""
    cur = {"smoothing_min_cutoff": 1000}
    ctrl = make_ctrl("relative", cursor=cur, stable_frames=2)
    run(ctrl, [(Gesture.PALM, moving_hand(i)) for i in range(4)])
    outs = run(ctrl, [(Gesture.PINCH_INDEX, moving_hand(4))], t0=4 * DT)
    assert flat(outs) == []


def test_right_click_does_not_move():
    cur = {"smoothing_min_cutoff": 1000}
    ctrl = make_ctrl("relative", cursor=cur, stable_frames=1)
    run(ctrl, [(Gesture.PALM, moving_hand(i)) for i in range(3)])
    outs = flat(run(ctrl, [(Gesture.PINCH_MIDDLE, moving_hand(i)) for i in range(3, 6)], t0=3 * DT))
    assert outs == [Click("right")]


# ---------- 捲動慣性 ----------

def two(i, dy):
    return make_hand(index=True, middle=True, offset=(0, dy * i))


def flick(ctrl, dy, n=6):
    """雙指快速移動 n 幀，然後換成張開手掌（靜止）。回傳換手勢後的捲動格數。"""
    run(ctrl, [(Gesture.TWO_FINGER, two(i, dy)) for i in range(n)])
    after = flat(run(ctrl, [(Gesture.PALM, make_hand())] * 60, t0=n * DT))
    return [c for c in after if isinstance(c, Scroll)]


def test_fast_flick_keeps_scrolling_and_slows_down():
    ctrl = make_ctrl(stable_frames=1, scroll_sensitivity=100)
    scrolls = flick(ctrl, -0.03)      # 手往上甩 → 往上捲
    assert scrolls and all(s.steps > 0 for s in scrolls)
    assert not ctrl.inertia_active   # 2 秒內會停下來


def test_slow_scroll_has_no_inertia():
    ctrl = make_ctrl(stable_frames=1, scroll_sensitivity=100)
    assert flick(ctrl, -0.001) == []


def test_inertia_can_be_disabled():
    ctrl = make_ctrl(stable_frames=1, scroll_sensitivity=100, scroll_inertia=False)
    assert flick(ctrl, -0.03) == []


def test_new_scroll_or_click_stops_inertia():
    ctrl = make_ctrl(stable_frames=1, scroll_sensitivity=100)
    run(ctrl, [(Gesture.TWO_FINGER, two(i, -0.03)) for i in range(6)])
    run(ctrl, [(Gesture.PALM, make_hand())] * 2, t0=6 * DT)
    assert ctrl.inertia_active
    run(ctrl, [(Gesture.PINCH_INDEX, make_hand())], t0=8 * DT)
    assert not ctrl.inertia_active


def test_inertia_continues_when_hand_leaves():
    ctrl = make_ctrl(stable_frames=1, scroll_sensitivity=100)
    run(ctrl, [(Gesture.TWO_FINGER, two(i, 0.03)) for i in range(6)])
    after = flat(run(ctrl, [(Gesture.NONE, None)] * 10, t0=6 * DT))
    assert any(isinstance(c, Scroll) and c.steps < 0 for c in after)


# ---------- 食指捏合：輕捏 = 左鍵、捏著移動 = 拖曳、捏住不動 = 右鍵 ----------

def smart_ctrl(**kw):
    cur = {"smoothing_min_cutoff": 1000}
    return make_ctrl("relative", cursor=cur, stable_frames=1, click_lock_seconds=0.1, **kw)


def test_quick_pinch_is_left_click():
    ctrl = smart_ctrl()
    hand = make_hand()
    run(ctrl, [(Gesture.PALM, hand)] * 2)
    pinch = flat(run(ctrl, [(Gesture.PINCH_INDEX, hand)] * 5, t0=2 * DT))
    assert pinch == []                         # 捏著時還不知道要做什麼
    release = flat(run(ctrl, [(Gesture.PALM, hand)], t0=7 * DT))
    assert release == [Click("left")]


def test_pinch_hold_still_is_right_click():
    ctrl = smart_ctrl(right_hold_seconds=0.6)
    hand = make_hand()
    run(ctrl, [(Gesture.PALM, hand)] * 2)
    held = flat(run(ctrl, [(Gesture.PINCH_INDEX, hand)] * 30, t0=2 * DT))   # 1 秒
    assert held == [Click("right")]
    release = flat(run(ctrl, [(Gesture.PALM, hand)], t0=40 * DT))
    assert release == []                       # 右鍵後放開不再點左鍵


def test_pinch_and_move_is_drag():
    ctrl = smart_ctrl(drag_threshold_px=25)
    run(ctrl, [(Gesture.PALM, moving_hand(0))] * 2)
    cmds = flat(run(ctrl, [(Gesture.PINCH_INDEX, moving_hand(i, 0.01)) for i in range(15)], t0=2 * DT))
    assert cmds[0] == Press("left")
    assert isinstance(cmds[1], MoveBy)         # 補上判斷期間已移動的距離
    assert sum(c.dx for c in cmds if isinstance(c, MoveBy)) > 25
    assert Click("right") not in cmds
    end = flat(run(ctrl, [(Gesture.PALM, moving_hand(14, 0.01))], t0=20 * DT))
    assert end == [Release("left")]


def test_jitter_during_lock_does_not_start_drag():
    ctrl = smart_ctrl(drag_threshold_px=25)
    run(ctrl, [(Gesture.PALM, make_hand())] * 2)
    # 捏合瞬間手抖一大下（在鎖定時間內），之後不動
    frames = [(Gesture.PINCH_INDEX, make_hand(offset=(0.03, 0.02)))] + [(Gesture.PINCH_INDEX, make_hand(offset=(0.03, 0.02)))] * 4
    cmds = flat(run(ctrl, frames, t0=2 * DT))
    assert Press("left") not in cmds
    assert flat(run(ctrl, [(Gesture.PALM, make_hand(offset=(0.03, 0.02)))], t0=8 * DT)) == [Click("left")]


def test_hand_lost_during_pinch_does_not_click():
    ctrl = smart_ctrl()
    run(ctrl, [(Gesture.PINCH_INDEX, make_hand())] * 3)
    assert flat(run(ctrl, [(Gesture.NONE, None)], t0=3 * DT)) == []


def test_middle_pinch_still_right_clicks():
    ctrl = smart_ctrl()
    assert flat(run(ctrl, [(Gesture.PINCH_MIDDLE, make_hand())] * 3)) == [Click("right")]
