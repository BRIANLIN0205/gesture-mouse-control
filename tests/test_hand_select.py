import pytest

from gesture_mouse.config import config_from_dict
from gesture_mouse.hand import DetectedHand, select_hand
from tests.handgen import make_hand

RIGHT = DetectedHand(make_hand(offset=(0.2, 0)), "right", 0.9)
LEFT = DetectedHand(make_hand(index=False, offset=(-0.2, 0)), "left", 0.95)


def test_picks_control_hand_when_both_visible():
    assert select_hand([LEFT, RIGHT], "right") is RIGHT.landmarks
    assert select_hand([RIGHT, LEFT], "right") is RIGHT.landmarks    # 順序不影響
    assert select_hand([LEFT, RIGHT], "left") is LEFT.landmarks


def test_other_hand_alone_is_ignored():
    assert select_hand([LEFT], "right") is None
    assert select_hand([], "right") is None


def test_any_takes_most_confident():
    assert select_hand([RIGHT, LEFT], "any") is LEFT.landmarks
    assert select_hand([RIGHT], "any") is RIGHT.landmarks


def test_two_hands_labelled_same_side_takes_most_confident():
    other = DetectedHand(make_hand(), "right", 0.5)
    assert select_hand([other, RIGHT], "right") is RIGHT.landmarks


def test_control_hand_config():
    assert config_from_dict({}).detection.control_hand == "right"
    assert config_from_dict({"detection": {"control_hand": "left"}}).detection.control_hand == "left"
    with pytest.raises(ValueError):
        config_from_dict({"detection": {"control_hand": "both"}})


def test_alternating_hands_do_not_move_cursor_to_other_hand():
    """兩手同框、每幀偵測順序互換：游標只跟右手，左手的位置不會讓游標跳。"""
    from gesture_mouse.controller import Controller, MoveBy
    from gesture_mouse.gestures import Gesture, GestureClassifier

    cfg = config_from_dict({"control": {"stable_frames": 1}, "cursor": {"smoothing_min_cutoff": 1000}})
    ctrl = Controller(cfg, (1920, 1080))
    clf = GestureClassifier()
    palm = dict(index=True, middle=True, ring=True, pinky=True)
    moves = []
    for i in range(20):
        right = DetectedHand(make_hand(offset=(0.1, 0), **palm), "right")
        left = DetectedHand(make_hand(index=False, offset=(-0.3, 0)), "left")   # 左手握拳
        hands = [left, right] if i % 2 else [right, left]
        lm = select_hand(hands, "right")
        cmds = ctrl.update(clf.classify(lm), lm, i / 30)
        moves += [c for c in cmds if isinstance(c, MoveBy)]
    assert moves == []          # 右手沒動 → 游標不動
    assert ctrl.active == Gesture.PALM and not ctrl.paused
