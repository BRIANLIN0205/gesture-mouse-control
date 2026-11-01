import pytest

from gesture_mouse.config import Config, config_from_dict, load_config
from gesture_mouse.gestures import Gesture
from gesture_mouse.smoothing import OneEuroFilter, PointFilter


def test_filter_first_value_passthrough():
    assert OneEuroFilter()(100.0, 0.0) == 100.0


def test_filter_reduces_jitter():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    out = [f(100 + (5 if i % 2 else -5), i / 30) for i in range(60)]
    late = out[30:]
    assert max(late) - min(late) < 10 * 0.5      # 抖動幅度明顯變小


def test_filter_converges_to_constant():
    f = PointFilter()
    x = y = None
    for i in range(200):
        x, y = f(500.0, 300.0, i / 30)
    assert abs(x - 500) < 1e-3 and abs(y - 300) < 1e-3


def test_filter_reset():
    f = OneEuroFilter()
    f(0.0, 0.0)
    f.reset()
    assert f(50.0, 1.0) == 50.0


def test_default_config():
    cfg = Config()
    assert cfg.action_for(Gesture.PALM) == "move_cursor"
    assert cfg.action_for(Gesture.POINT) == "none"
    assert cfg.action_for(Gesture.PINCH_INDEX) == "pinch_smart"
    assert cfg.action_for(Gesture.FIST) == "toggle_pause"
    assert cfg.action_for(Gesture.NONE) == "none"


def test_repo_config_file_loads(tmp_path):
    from pathlib import Path

    cfg = load_config(Path(__file__).resolve().parent.parent / "config.yaml")
    assert cfg.camera.mirror is True
    assert cfg.gestures["two_finger"] == "scroll"


def test_partial_config_keeps_defaults():
    cfg = config_from_dict({"cursor": {"frame_margin": 0.2}, "gestures": {"fist": "none"}})
    assert cfg.cursor.frame_margin == 0.2
    assert cfg.cursor.pointer_landmark == 5
    assert cfg.gestures["fist"] == "none"
    assert cfg.gestures["palm"] == "move_cursor"


@pytest.mark.parametrize(
    "data",
    [
        {"cursor": {"typo": 1}},
        {"gestures": {"wave": "click_left"}},
        {"gestures": {"palm": "fly"}},
        {"unknown_section": {}},
        {"cursor": {"mode": "teleport"}},
    ],
)
def test_invalid_config_raises(data):
    with pytest.raises(ValueError):
        config_from_dict(data)


def test_missing_config_file():
    with pytest.raises(FileNotFoundError):
        load_config("does-not-exist.yaml")
