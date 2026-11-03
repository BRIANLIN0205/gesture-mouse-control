import os

import pytest
import yaml

from gesture_mouse.config import Config, config_from_dict, load_config
from gesture_mouse.live_config import ConfigWatcher, apply_config
from gesture_mouse.settings_gui import all_fields, get_value, save_values
from gesture_mouse.yaml_update import update_yaml_text
from pathlib import Path

REPO_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def test_update_keeps_comments_and_changes_value():
    text = "cursor:\n  mode: relative   # 註解\n  relative_gain: 1.5      # 倍率\n\nshow_preview: true\n"
    out = update_yaml_text(text, {"cursor": {"relative_gain": 2.25}, "show_preview": False})
    assert "  relative_gain: 2.25      # 倍率" in out
    assert "  mode: relative   # 註解" in out
    assert "show_preview: false" in out
    assert yaml.safe_load(out)["cursor"]["relative_gain"] == 2.25


def test_update_adds_missing_key_and_section():
    text = "cursor:\n  mode: relative\n\ngestures:\n  palm: move_cursor\n"
    out = update_yaml_text(text, {"cursor": {"relative_gain": 3.0}, "sound": {"enabled": False}})
    data = yaml.safe_load(out)
    assert data["cursor"] == {"mode": "relative", "relative_gain": 3.0}
    assert data["sound"] == {"enabled": False}
    assert data["gestures"] == {"palm": "move_cursor"}


def test_update_strings_with_hash_and_spaces():
    text = 'sound:\n  pause_file: ""       # 自訂\n'
    out = update_yaml_text(text, {"sound": {"pause_file": "C:\\My Sounds\\a #1.wav"}})
    assert yaml.safe_load(out)["sound"]["pause_file"] == "C:\\My Sounds\\a #1.wav"
    assert "# 自訂" in out


def test_rewriting_repo_config_with_same_values_is_noop_semantically():
    text = REPO_CONFIG.read_text(encoding="utf-8")
    cfg = load_config(REPO_CONFIG)
    data = {}
    for f in all_fields():
        if "." in f.key:
            sec, name = f.key.split(".", 1)
            data.setdefault(sec, {})[name] = get_value(cfg, f.key)
        else:
            data[f.key] = get_value(cfg, f.key)
    out = update_yaml_text(text, data)
    assert config_from_dict(yaml.safe_load(out)) == cfg
    assert out.count("#") == text.count("#")


def test_every_field_exists_and_default_in_range():
    defaults = Config()
    for f in all_fields():
        value = get_value(defaults, f.key)   # 欄位名稱打錯會丟 AttributeError
        if f.kind in ("float", "int"):
            assert f.lo <= value <= f.hi, f.key
        if f.kind == "choice":
            assert value in [c[0] for c in f.choices], f.key


def test_save_values_rejects_invalid_and_keeps_file(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(REPO_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    before = p.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        save_values(p, {"cursor.mode": "weird"})
    assert p.read_text(encoding="utf-8") == before
    cfg = save_values(p, {"cursor.relative_gain": 2.0})
    assert cfg.cursor.relative_gain == 2.0
    assert load_config(p).cursor.relative_gain == 2.0


def test_apply_config_in_place_and_restart_keys():
    cfg = Config()
    cursor = cfg.cursor
    new = Config()
    new.cursor.relative_gain = 3.0
    new.camera.index = 1
    new.gestures["point"] = "click_left"
    changed, restart = apply_config(cfg, new)
    assert cursor.relative_gain == 3.0          # 同一個物件被更新
    assert cfg.camera.index == 0                # 要重開的不套用
    assert restart == {"camera.index"}
    assert cfg.gestures["point"] == "click_left"
    assert "cursor.relative_gain" in changed


def test_watcher_reloads_on_change(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("cursor:\n  relative_gain: 1.0\n", encoding="utf-8")
    w = ConfigWatcher(p, interval=0)
    assert w.poll(1.0) is None
    p.write_text("cursor:\n  relative_gain: 2.0\n", encoding="utf-8")
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 5))
    cfg = w.poll(2.0)
    assert cfg is not None and cfg.cursor.relative_gain == 2.0
    # 格式錯誤：不丟例外，回傳 None
    p.write_text("cursor:\n  nope: 1\n", encoding="utf-8")
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 10))
    assert w.poll(3.0) is None


def test_set_paused_releases_and_reports():
    from gesture_mouse.controller import Controller, PauseChanged

    c = Controller(Config(), (1920, 1080))
    cmds = c.set_paused(True)
    assert c.paused and any(isinstance(x, PauseChanged) and x.paused for x in cmds)
    assert c.set_paused(True) == []


def test_settings_window_builds_and_saves(tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from gesture_mouse.settings_gui import build_window

    _app = QApplication.instance() or QApplication([])  # noqa: F841  視窗需要 QApplication
    p = tmp_path / "config.yaml"
    p.write_text(REPO_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    win = build_window(p)
    win.changed("cursor.relative_gain", 2.5)
    win.changed("camera.index", 1)
    assert win.save()
    assert load_config(p).cursor.relative_gain == 2.5
    assert "重開" in win.status.text()
    win.close()


def test_tray_icon_creates_qapplication_first(monkeypatch):
    # 回歸測試：沒有 QApplication 就呼叫 isSystemTrayAvailable() 會讓 Windows 閃退
    pytest.importorskip("PySide6.QtWidgets")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    from gesture_mouse.tray import TrayIcon

    seen = []
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable",
                        staticmethod(lambda: seen.append(QApplication.instance() is not None) or False))
    tray = TrayIcon(None)
    assert seen == [True]
    assert not tray.enabled
