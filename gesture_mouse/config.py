"""讀取 config.yaml，缺少的欄位使用預設值。"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from .gestures import Gesture

# 可以指定給手勢的動作
ACTIONS = {
    "move_cursor",   # 移動游標
    "hold_left",     # 按住左鍵（放開手勢才放開；按住時移動就是拖曳）
    "hold_right",    # 按住右鍵
    "click_left",    # 左鍵單擊
    "click_right",   # 右鍵單擊
    "double_click",  # 左鍵雙擊
    "scroll",        # 上下移動手來捲動
    "toggle_pause",  # 維持一段時間後切換暫停 / 恢復
    "none",          # 不做事
}

DEFAULT_GESTURE_ACTIONS: Dict[str, str] = {
    Gesture.PALM.value: "move_cursor",
    Gesture.POINT.value: "none",
    Gesture.PINCH_INDEX.value: "hold_left",
    Gesture.PINCH_MIDDLE.value: "click_right",
    Gesture.TWO_FINGER.value: "scroll",
    Gesture.FIST.value: "toggle_pause",
}


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 640
    height: int = 480
    mirror: bool = True


@dataclass
class DetectionConfig:
    min_detection_confidence: float = 0.7
    min_tracking_confidence: float = 0.6
    pinch_enter: float = 0.25
    pinch_exit: float = 0.35
    extend_ratio: float = 1.1


@dataclass
class CursorConfig:
    mode: str = "relative"           # relative = 像觸控板（手的位移帶動游標）；absolute = 手的位置直接對應螢幕位置
    pointer_landmark: int = 5        # 5 = 食指根部（捏合時較穩），8 = 食指指尖
    # 相對模式
    relative_gain: float = 1.0       # 基本倍率：慢慢移動時，手移過整個鏡頭畫面寬 = 游標移過整個螢幕寬 × 倍率
    relative_accel: float = 1.5      # 加速度：移動越快倍率越大，0 = 不加速
    relative_max_gain: float = 4.0   # 加速後的倍率上限
    relative_deadzone: float = 0.8   # 每幀小於幾像素的移動忽略（消除手靜止時的飄移）
    # 絕對模式
    frame_margin: float = 0.15       # 畫面四周留白比例，手不用移到鏡頭邊緣就能碰到螢幕邊
    smoothing_min_cutoff: float = 1.0
    smoothing_beta: float = 0.01


@dataclass
class ControlConfig:
    stable_frames: int = 2           # 手勢要連續幾幀一致才生效，避免閃動誤觸
    scroll_sensitivity: float = 40.0 # 手移動整個畫面高度 = 捲動幾格
    scroll_invert: bool = False
    pause_hold_seconds: float = 1.5  # 握拳要維持多久才切換暫停（短握拳 = 抬起，游標停住）
    click_lock_seconds: float = 0.15 # 捏合（點擊）開始後鎖住游標多久，避免捏合時手抖把點擊點歪
    scroll_inertia: bool = True      # 捲動手勢結束時若還在快速移動，繼續捲動並慢慢減速
    scroll_inertia_min_speed: float = 15.0  # 結束時速度超過每秒幾格才觸發慣性
    scroll_inertia_friction: float = 3.0    # 慣性減速快慢，越大停得越快


@dataclass
class SoundConfig:
    enabled: bool = True
    volume: float = 0.5        # 內建提示音音量 0~1
    pause_file: str = ""       # 自訂暫停音效 wav 路徑，留空 = 內建提示音（低音）
    resume_file: str = ""      # 自訂恢復音效 wav 路徑，留空 = 內建提示音（高音）


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    sound: SoundConfig = field(default_factory=SoundConfig)
    gestures: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_GESTURE_ACTIONS))
    show_preview: bool = True

    def action_for(self, gesture: Gesture) -> str:
        return self.gestures.get(gesture.value, "none")


def _fill(cls: Any, data: Optional[Dict[str, Any]], section: str) -> Any:
    data = data or {}
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"設定檔 [{section}] 有不認得的欄位：{', '.join(sorted(unknown))}")
    return cls(**data)


def config_from_dict(data: Optional[Dict[str, Any]]) -> Config:
    data = dict(data or {})
    cfg = Config(
        camera=_fill(CameraConfig, data.pop("camera", None), "camera"),
        detection=_fill(DetectionConfig, data.pop("detection", None), "detection"),
        cursor=_fill(CursorConfig, data.pop("cursor", None), "cursor"),
        control=_fill(ControlConfig, data.pop("control", None), "control"),
        sound=_fill(SoundConfig, data.pop("sound", None), "sound"),
    )

    gestures = dict(DEFAULT_GESTURE_ACTIONS)
    gestures.update(data.pop("gestures", None) or {})
    valid_gestures = {g.value for g in Gesture} - {Gesture.NONE.value}
    for name, action in gestures.items():
        if name not in valid_gestures:
            raise ValueError(f"不認得的手勢：{name}（可用：{', '.join(sorted(valid_gestures))}）")
        if action not in ACTIONS:
            raise ValueError(f"手勢 {name} 的動作 {action} 不存在（可用：{', '.join(sorted(ACTIONS))}）")
    cfg.gestures = gestures

    if cfg.cursor.mode not in ("relative", "absolute"):
        raise ValueError(f"cursor.mode 只能是 relative 或 absolute，收到 {cfg.cursor.mode}")

    if "show_preview" in data:
        cfg.show_preview = bool(data.pop("show_preview"))
    if data:
        raise ValueError(f"設定檔有不認得的欄位：{', '.join(sorted(data))}")
    return cfg


def load_config(path: Optional[Union[str, Path]] = None) -> Config:
    if path is None:
        return Config()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到設定檔：{p}")
    with p.open("r", encoding="utf-8") as f:
        return config_from_dict(yaml.safe_load(f))
