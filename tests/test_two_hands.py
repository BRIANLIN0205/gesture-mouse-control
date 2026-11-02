from gesture_mouse.config import TwoHandsConfig, config_from_dict
from gesture_mouse.controller import Hotkey, Zoom
from gesture_mouse.gestures import Gesture
from gesture_mouse.hand import DetectedHand, select_other_hand
from gesture_mouse.sounds import SoundPlayer
from gesture_mouse.overlay import overlay_status
from gesture_mouse.controller import Controller
from gesture_mouse.two_hands import VOLUME_DOWN, VOLUME_UP, TwoHandController

from .handgen import make_hand

P = Gesture.PINCH_INDEX
M = Gesture.PINCH_MIDDLE


def pinch_hand(x):
    """食指捏拇指的手，整隻手平移到 x 附近。"""
    h = make_hand(index=True, thumb_tip=(0.44, 0.40))
    return [(p[0] + x - 0.5, p[1], p[2]) for p in h]


def hand_at(y):
    h = make_hand()
    return [(p[0], p[1] + y, p[2]) for p in h]


def zoom_steps(cmds):
    return sum(c.steps for c in cmds if isinstance(c, Zoom))


def test_spreading_both_pinches_zooms_in():
    two = TwoHandController(TwoHandsConfig())
    out = []
    for i, gap in enumerate([0.10, 0.10, 0.12, 0.15, 0.20, 0.30]):
        out += two.update(P, pinch_hand(0.5 + gap), P, pinch_hand(0.5 - gap), i * 0.03)
    assert two.zooming
    assert zoom_steps(out) > 0


def test_closing_both_pinches_zooms_out():
    two = TwoHandController(TwoHandsConfig())
    out = []
    for i, gap in enumerate([0.30, 0.30, 0.25, 0.20, 0.15, 0.10]):
        out += two.update(P, pinch_hand(0.5 + gap), P, pinch_hand(0.5 - gap), i * 0.03)
    assert zoom_steps(out) < 0


def test_holding_still_does_not_zoom():
    two = TwoHandController(TwoHandsConfig())
    out = []
    for i in range(10):
        out += two.update(P, pinch_hand(0.7), P, pinch_hand(0.3), i * 0.03)
    assert zoom_steps(out) == 0


def test_one_hand_pinch_is_not_zoom():
    two = TwoHandController(TwoHandsConfig())
    for i in range(5):
        two.update(P, pinch_hand(0.7), Gesture.PALM, make_hand(), i * 0.03)
    assert not two.zooming


def test_main_stays_blocked_until_main_releases_pinch():
    two = TwoHandController(TwoHandsConfig())
    for i in range(3):
        two.update(P, pinch_hand(0.7), P, pinch_hand(0.3), i * 0.03)
    assert two.main_blocked
    two.update(P, pinch_hand(0.7), Gesture.PALM, make_hand(), 0.2)   # 左手先放開
    assert not two.zooming and two.main_blocked                     # 右手還捏著：不能點擊
    two.update(Gesture.PALM, make_hand(), Gesture.PALM, make_hand(), 0.3)
    assert not two.main_blocked


def test_zoom_disabled():
    two = TwoHandController(TwoHandsConfig(zoom=False))
    for i in range(5):
        two.update(P, pinch_hand(0.7), P, pinch_hand(0.3), i * 0.03)
    assert not two.zooming and not two.main_blocked


def test_other_hand_middle_pinch_up_raises_volume():
    two = TwoHandController(TwoHandsConfig())
    out = []
    t = 0.0
    for y in [0, 0, 0, -0.05, -0.1, -0.15, -0.2, -0.2, -0.2]:
        out += two.update(Gesture.NONE, None, M, hand_at(y), t)
        t += 0.1
    assert out and all(c == VOLUME_UP for c in out)
    assert len(out) >= 3          # 離越遠調越快，持續按


def test_other_hand_middle_pinch_down_lowers_volume():
    two = TwoHandController(TwoHandsConfig())
    out = []
    for i, y in enumerate([0, 0, 0.1, 0.1]):
        out += two.update(Gesture.PALM, make_hand(), M, hand_at(y), i * 0.1)
    assert out and all(c == VOLUME_DOWN for c in out)


def test_volume_deadzone_and_pause():
    two = TwoHandController(TwoHandsConfig())
    out = []
    for i in range(6):
        out += two.update(Gesture.NONE, None, M, hand_at(0.01 * (i % 2)), i * 0.1)
    assert out == []
    two = TwoHandController(TwoHandsConfig())
    for i, y in enumerate([0, 0, 0.2, 0.2]):
        out += two.update(Gesture.NONE, None, M, hand_at(y), i * 0.1, paused=True)
    assert out == []


def test_select_other_hand():
    r, l = make_hand(), make_hand()
    hands = [DetectedHand(r, "right", 0.9), DetectedHand(l, "left", 0.8)]
    assert select_other_hand(hands, "right", r) is l
    assert select_other_hand(hands, "left", l) is r
    assert select_other_hand(hands, "any", r) is l
    assert select_other_hand([DetectedHand(r, "right")], "right", r) is None
    # 主控手不在畫面上，另一隻手仍然可以調音量
    assert select_other_hand([DetectedHand(l, "left")], "right", None) is l


def test_volume_keys_have_no_click_sound():
    sp = SoundPlayer(config_from_dict({}).sound)
    assert sp.sound_for([VOLUME_UP]) is None
    assert sp.sound_for([Hotkey(("alt", "left"), "back")]) is not None


def test_overlay_shows_two_hand_status():
    ctrl = Controller(config_from_dict({}), (1920, 1080))
    two = TwoHandController(TwoHandsConfig())
    two.zooming = True
    assert overlay_status(ctrl, True, False, two) == "zoom"
    two.zooming, two.volume_active = False, True
    assert overlay_status(ctrl, True, False, two) == "volume"


def test_config_two_hands_section():
    cfg = config_from_dict({"two_hands": {"zoom": False, "volume_max_speed": 5}})
    assert cfg.two_hands.zoom is False and cfg.two_hands.volume_max_speed == 5


def test_zoom_never_clicks_with_main_hand():
    """模擬 app 的流程：右手先捏、左手跟著捏來縮放，放開後不能多出左鍵點擊。"""
    from gesture_mouse.controller import Click, Press

    ctrl = Controller(config_from_dict({}), (1920, 1080))
    two = TwoHandController(TwoHandsConfig())
    out = []
    frames = (
        [(P, pinch_hand(0.7), Gesture.PALM, make_hand())] * 2
        + [(P, pinch_hand(0.7 + d), P, pinch_hand(0.3 - d)) for d in (0, 0, 0.05, 0.1, 0.15)]
        + [(P, pinch_hand(0.85), Gesture.PALM, make_hand())] * 3      # 左手先放開，右手還捏著
        + [(Gesture.PALM, make_hand(), Gesture.PALM, make_hand())] * 3
    )
    for i, (g, lm, og, olm) in enumerate(frames):
        t = i * 0.03
        tc = two.update(g, lm, og, olm, t)
        cmds = ctrl.update(Gesture.NONE, None, t) if two.main_blocked else ctrl.update(g, lm, t)
        out += cmds + tc
    assert zoom_steps(out) > 0
    assert not any(isinstance(c, (Click, Press)) for c in out)
