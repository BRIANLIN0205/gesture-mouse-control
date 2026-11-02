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
    "move_flick_scroll",  # 移動游標；快速上下甩 = 捲動（帶慣性）、左右甩 = 上一頁 / 下一頁
    "pinch_smart",   # 輕捏 = 左鍵點擊；捏著移動 = 拖曳；捏住不動一段時間 = 右鍵
    "hold_left",     # 按住左鍵（放開手勢才放開；按住時移動就是拖曳）
    "hold_right",    # 按住右鍵
    "click_left",    # 左鍵單擊
    "click_right",   # 右鍵單擊
    "double_click",  # 左鍵雙擊
    "joystick",      # 搖桿：捏住時上下偏離起點越遠捲越快；快速放開 = 方向鍵上 / 下；左右偏移放開 = 上一頁 / 下一頁
    "scroll",        # 上下移動手來捲動（慢慢移動就捲，舊做法）
    "flick_scroll",  # 快速上下甩 = 捲動（帶慣性）；左右甩 = 上一頁 / 下一頁
    "flick_windows", # 快速上甩 = 所有視窗、下甩 = 顯示桌面、左右甩 = 切換視窗
    "toggle_pause",  # 維持一段時間後切換暫停 / 恢復
    "none",          # 不做事
}

DEFAULT_GESTURE_ACTIONS: Dict[str, str] = {
    Gesture.PALM.value: "move_cursor",
    Gesture.POINT.value: "none",
    Gesture.PINCH_INDEX.value: "pinch_smart",
    Gesture.PINCH_MIDDLE.value: "joystick",
    Gesture.TWO_FINGER.value: "none",
    Gesture.THREE_FINGER.value: "flick_windows",
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
    control_hand: str = "right"      # 主控手：right / left；any = 不分左右（兩手同框時取信心最高的）
    swap_hands: bool = False         # 左右手判斷相反時設 true（預覽視窗手腕旁會標 L / R）
    edge_margin: float = 0.03        # 手離畫面邊緣小於這個比例時提示「快出畫面了」


@dataclass
class CursorConfig:
    mode: str = "relative"           # relative = 像觸控板（手的位移帶動游標）；absolute = 手的位置直接對應螢幕位置
    pointer_landmark: int = 5        # 5 = 食指根部（捏合時較穩），8 = 食指指尖
    # 相對模式
    relative_gain: float = 1.5       # 基本倍率：慢慢移動時，手移過整個鏡頭畫面寬 = 游標移過整個螢幕寬 × 倍率
    relative_accel: float = 1.5      # 加速度：移動越快倍率越大，0 = 不加速
    relative_max_gain: float = 6.0   # 加速後的倍率上限
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
    drag_threshold_px: float = 25.0  # pinch_smart：捏著移動超過幾像素才算拖曳
    right_hold_seconds: float = 0.6  # pinch_smart：捏住不動多久算右鍵
    scroll_inertia: bool = True      # 捲動手勢結束時若還在快速移動，繼續捲動並慢慢減速
    scroll_inertia_min_speed: float = 15.0  # 結束時速度超過每秒幾格才觸發慣性
    scroll_inertia_friction: float = 3.0    # 慣性減速快慢，越大停得越快
    # 搖桿（中指捏拇指）
    joystick_deadzone: float = 0.03  # 離起點不到畫面高的幾成不捲動（避免手抖）
    joystick_full: float = 0.20      # 偏到畫面高的幾成時達到最高速
    joystick_max_speed: float = 30.0 # 最高每秒捲幾格
    joystick_tap_seconds: float = 0.4  # 捏住不到這麼久就放開 = 方向鍵上 / 下
    joystick_nav_distance: float = 0.08  # 左右偏超過畫面寬的幾成，放開時翻頁
    # 手掌甩動（palm 設為 move_flick_scroll 時才有作用）
    palm_flick_nav: bool = True      # 手掌快速左右甩 = 上一頁 / 下一頁
    palm_swipe_min_speed: float = 2.0  # 手掌甩動捲動的速度門檻（比雙指 / 三指高，避免快速移動游標被誤判）
    swipe_min_speed: float = 1.2     # 雙指 / 三指甩動判定：手的速度至少每秒幾個畫面高
    swipe_min_distance: float = 0.08 # 甩動判定：0.2 秒內至少移動畫面高的幾成
    swipe_cooldown: float = 0.5      # 一次甩動後多久內不再判定（避免手收回來時誤判反方向）
    flick_scroll_gain: float = 20.0  # 甩動捲動：甩動速度 × 這個值 = 一開始每秒捲幾格


@dataclass
class TwoHandsConfig:
    # 雙手縮放：兩手都用食指捏拇指，拉開 = 放大、靠近 = 縮小（送出 Ctrl + 滾輪）
    zoom: bool = True
    zoom_step: float = 0.15          # 兩手距離每變化幾成算縮放一格
    # 另一隻手（預設左手）調音量：中指捏拇指上下移，像搖桿
    volume: bool = True
    volume_deadzone: float = 0.03    # 離起點不到畫面高的幾成不調整
    volume_full: float = 0.20        # 偏到畫面高的幾成時達到最快
    volume_max_speed: float = 10.0   # 最快每秒按幾下音量鍵（Windows 每下約 2%）


@dataclass
class OverlayConfig:
    enabled: bool = True       # 游標旁顯示狀態小圓圈（不開預覽視窗也知道系統怎麼解讀你的手）
    size: int = 16             # 圓圈直徑（像素）
    offset: int = 18           # 離游標多遠（往右下）


@dataclass
class SoundConfig:
    enabled: bool = True
    volume: float = 0.5        # 內建提示音音量 0~1
    pause_file: str = ""       # 自訂暫停音效 wav 路徑，留空 = 內建提示音（低音）
    resume_file: str = ""      # 自訂恢復音效 wav 路徑，留空 = 內建提示音（高音）
    click_enabled: bool = True # 點擊 / 開始拖曳時播放輕微的「喀」聲
    click_volume: float = 0.25
    click_file: str = ""       # 自訂點擊音效 wav 路徑，留空 = 內建


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    sound: SoundConfig = field(default_factory=SoundConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    two_hands: TwoHandsConfig = field(default_factory=TwoHandsConfig)
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
        overlay=_fill(OverlayConfig, data.pop("overlay", None), "overlay"),
        two_hands=_fill(TwoHandsConfig, data.pop("two_hands", None), "two_hands"),
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

    if cfg.detection.control_hand not in ("right", "left", "any"):
        raise ValueError(f"detection.control_hand 只能是 right、left 或 any，收到 {cfg.detection.control_hand}")
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
