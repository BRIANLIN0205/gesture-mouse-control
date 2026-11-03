import pytest

from gesture_mouse.gestures import Gesture, GestureClassifier
from tests.handgen import make_hand

INDEX_TIP = (0.44, 0.40)
MIDDLE_TIP = (0.50, 0.40)


@pytest.fixture
def clf():
    # 嚴格模式：測原本的手勢判斷規則（寬鬆移動與出畫面保持另外測）
    return GestureClassifier(loose_palm=False, edge_hold=False)


def test_no_hand(clf):
    assert clf.classify(None) == Gesture.NONE


def test_index_only_is_point(clf):
    assert clf.classify(make_hand(index=True)) == Gesture.POINT


def test_index_and_middle_is_two_finger(clf):
    assert clf.classify(make_hand(index=True, middle=True)) == Gesture.TWO_FINGER


def test_all_folded_is_fist(clf):
    assert clf.classify(make_hand(index=False)) == Gesture.FIST


def test_open_palm_is_palm(clf):
    assert clf.classify(make_hand(index=True, middle=True, ring=True, pinky=True)) == Gesture.PALM


def test_three_fingers(clf):
    assert clf.classify(make_hand(index=True, middle=True, ring=True)) == Gesture.THREE_FINGER


def test_middle_ring_pinky_without_index_is_none(clf):
    assert clf.classify(make_hand(index=False, middle=True, ring=True, pinky=True)) == Gesture.NONE


def test_pinch_from_open_palm(clf):
    # 張開手掌時拇指碰食指（OK 手勢）也算左鍵捏合
    hand = make_hand(index=True, middle=True, ring=True, pinky=True, thumb_tip=(0.445, 0.41))
    assert clf.classify(hand) == Gesture.PINCH_INDEX


def test_thumb_on_index_is_pinch_index(clf):
    assert clf.classify(make_hand(index=True, thumb_tip=(0.445, 0.41))) == Gesture.PINCH_INDEX


def test_thumb_on_middle_is_pinch_middle(clf):
    hand = make_hand(index=True, middle=True, thumb_tip=(0.505, 0.41))
    assert clf.classify(hand) == Gesture.PINCH_MIDDLE


def test_pinch_hysteresis(clf):
    # 手大小 = 手腕到中指根部 = 0.2
    # 捏合門檻 0.25 → 距離 < 0.05；放開門檻 0.35 → 距離 > 0.07
    assert clf.classify(make_hand(thumb_tip=(0.44, 0.44))) == Gesture.PINCH_INDEX   # 距離 0.04
    # 距離 0.06：在兩個門檻之間，維持捏合
    assert clf.classify(make_hand(thumb_tip=(0.44, 0.46))) == Gesture.PINCH_INDEX
    # 距離 0.08：超過放開門檻
    assert clf.classify(make_hand(thumb_tip=(0.44, 0.48))) == Gesture.POINT
    # 距離 0.06 但先前沒捏合：不算捏合
    assert clf.classify(make_hand(thumb_tip=(0.44, 0.46))) == Gesture.POINT


def test_scale_invariant(clf):
    # 手離鏡頭遠（變小）時一樣能判斷
    small = make_hand(index=True, middle=True, scale=0.5)
    assert clf.classify(small) == Gesture.TWO_FINGER
    clf.reset()
    small_pinch = make_hand(index=True, scale=0.5, thumb_tip=None)
    # 縮小後指尖位置
    ix, iy = small_pinch[8][0], small_pinch[8][1]
    small_pinch[4] = (ix + 0.005, iy + 0.005, 0.0)
    assert clf.classify(small_pinch) == Gesture.PINCH_INDEX


def test_translation_invariant(clf):
    assert clf.classify(make_hand(index=True, offset=(0.2, -0.1))) == Gesture.POINT


def test_wrong_landmark_count(clf):
    with pytest.raises(ValueError):
        clf.classify([(0, 0, 0)] * 5)


def test_invalid_thresholds():
    with pytest.raises(ValueError):
        GestureClassifier(pinch_enter=0.4, pinch_exit=0.3)


def test_loose_palm_turns_unknown_into_palm():
    clf = GestureClassifier(loose_palm=True, edge_hold=False)
    # 小指、無名指被誤判彎曲以外的不明組合 → 還是移動
    assert clf.classify(make_hand(index=False, middle=True, ring=True, pinky=True)) == Gesture.PALM
    assert clf.classify(make_hand(index=True)) == Gesture.PALM
    # 握拳、雙指、三指、捏合不受影響
    assert clf.classify(make_hand(index=False)) == Gesture.FIST
    assert clf.classify(make_hand(index=True, middle=True)) == Gesture.TWO_FINGER
    assert clf.classify(make_hand(index=True, middle=True, ring=True)) == Gesture.THREE_FINGER
    assert clf.classify(make_hand(thumb_tip=(0.44, 0.44))) == Gesture.PINCH_INDEX


def _fingers_out_of_top(hand):
    """模擬手往上移出畫面：指節、指尖跑到畫面外，而且被 MediaPipe 猜成彎曲（指尖比指節靠近手腕）。"""
    pts = make_hand(index=True, middle=True, ring=True, pinky=True, offset=(0.0, -0.45))
    for base in (5, 9, 13, 17):
        x = pts[base][0]
        pts[base + 1] = (x, -0.05, 0.0)   # PIP
        pts[base + 2] = (x, -0.03, 0.0)
        pts[base + 3] = (x, -0.01, 0.0)   # 指尖：比 PIP 靠近手腕 → 判成彎曲
    return pts


def test_edge_hold_keeps_palm_when_fingers_leave_frame():
    clf = GestureClassifier(loose_palm=False, edge_hold=True)
    assert clf.classify(make_hand(index=True, middle=True, ring=True, pinky=True, offset=(0.0, -0.45))) == Gesture.PALM
    assert clf.classify(_fingers_out_of_top(None)) == Gesture.PALM


def test_without_edge_hold_fingers_out_of_frame_become_fist():
    clf = GestureClassifier(loose_palm=False, edge_hold=False)
    clf.classify(make_hand(index=True, middle=True, ring=True, pinky=True, offset=(0.0, -0.45)))
    assert clf.classify(_fingers_out_of_top(None)) == Gesture.FIST


def test_edge_hold_still_allows_fist_inside_frame():
    clf = GestureClassifier(loose_palm=True, edge_hold=True)
    assert clf.classify(make_hand(index=True, middle=True, ring=True, pinky=True)) == Gesture.PALM
    assert clf.classify(make_hand(index=False)) == Gesture.FIST


def test_edge_hold_no_new_pinch_when_tip_out_of_frame():
    clf = GestureClassifier(loose_palm=True, edge_hold=True)
    hand_ = make_hand(index=True, offset=(0.0, -0.45))
    tx, ty = hand_[8][0], hand_[8][1]
    assert ty < 0
    hand_[4] = (tx + 0.005, ty + 0.005, 0.0)
    assert clf.classify(hand_) != Gesture.PINCH_INDEX
