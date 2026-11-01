import io
import wave

from gesture_mouse.config import SoundConfig, config_from_dict
from gesture_mouse.controller import Controller, MoveBy, PauseChanged
from gesture_mouse.gestures import Gesture
from gesture_mouse.sounds import SoundPlayer, make_tone_wav
from tests.handgen import make_hand


def test_tone_is_valid_wav():
    data = make_tone_wav([587, 880], note_ms=90)
    with wave.open(io.BytesIO(data)) as w:
        assert w.getnchannels() == 1
        assert w.getnframes() == 2 * int(22050 * 0.09)


def test_pause_and_resume_sounds_differ():
    p = SoundPlayer(SoundConfig())
    assert p.pause_wav != p.resume_wav
    assert p.sound_for([PauseChanged(True)]) == p.pause_wav
    assert p.sound_for([PauseChanged(False)]) == p.resume_wav
    assert p.sound_for([MoveBy(1, 1)]) is None


def test_custom_wav_file(tmp_path):
    f = tmp_path / "ding.wav"
    f.write_bytes(make_tone_wav([1000]))
    p = SoundPlayer(SoundConfig(pause_file=str(f), resume_file=str(tmp_path / "missing.wav")))
    assert p.pause_wav == f.read_bytes()
    assert p.resume_wav == make_tone_wav([587, 880], volume=0.5)   # 找不到檔案 → 內建


def test_controller_emits_pause_changed_once_each_way():
    cfg = config_from_dict({"control": {"stable_frames": 1, "pause_hold_seconds": 0.5}})
    ctrl = Controller(cfg, (1920, 1080))
    fist = make_hand(index=False)
    t = 0.0
    events = []
    for _ in range(60):   # 握拳 2 秒
        events += [c for c in ctrl.update(Gesture.FIST, fist, t) if isinstance(c, PauseChanged)]
        t += 1 / 30
    assert events == [PauseChanged(True)]
    ctrl.update(Gesture.PALM, make_hand(), t)
    events = []
    for _ in range(60):
        t += 1 / 30
        events += [c for c in ctrl.update(Gesture.FIST, fist, t) if isinstance(c, PauseChanged)]
    assert events == [PauseChanged(False)]


def test_sound_config_section():
    cfg = config_from_dict({"sound": {"enabled": False}})
    assert cfg.sound.enabled is False
    assert cfg.sound.volume == 0.5
