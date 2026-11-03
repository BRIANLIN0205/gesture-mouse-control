"""手勢滑鼠設定視窗（PySide6）。

從系統匣圖示的「開啟設定」打開，也可以直接執行：python -m gesture_mouse.settings_gui
拉滑桿或勾選後會自動寫回 config.yaml（保留原本的註解），手勢程式會在半秒內套用。
標「需重開」的項目要關掉手勢程式再開才會生效。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import Config, config_from_dict, load_config
from .live_config import RESTART_KEYS
from .yaml_update import update_yaml_text

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


@dataclass
class Field:
    key: str            # 區塊.欄位，例如 cursor.relative_gain
    label: str
    kind: str           # float / int / bool / choice / file
    lo: float = 0.0
    hi: float = 1.0
    step: float = 0.01
    tip: str = ""
    choices: Tuple[Tuple[str, str], ...] = ()   # (值, 顯示文字)

    @property
    def restart(self) -> bool:
        return self.key in RESTART_KEYS


# (分頁名稱, [(小標題, [欄位...]), ...])
PAGES: List[Tuple[str, List[Tuple[str, List[Field]]]]] = [
    ("游標", [
        ("移動方式", [
            Field("cursor.mode", "模式", "choice", choices=(("relative", "相對（像觸控板）"), ("absolute", "絕對（手的位置對應螢幕位置）"))),
            Field("cursor.pointer_landmark", "游標跟著", "choice", choices=((5, "食指根部（捏合時較穩）"), (8, "食指指尖"))),
        ]),
        ("相對模式", [
            Field("cursor.relative_gain", "靈敏度", "float", 0.2, 5.0, 0.1, "慢慢移動時，手移過整個鏡頭畫面寬 = 游標移過幾個螢幕寬"),
            Field("cursor.relative_accel", "加速度", "float", 0.0, 5.0, 0.1, "移動越快游標走越遠；0 = 不加速"),
            Field("cursor.relative_max_gain", "加速上限", "float", 1.0, 15.0, 0.5, "加速後的倍率最多到多少"),
            Field("cursor.relative_deadzone", "防飄移", "float", 0.0, 5.0, 0.1, "每幀小於幾像素的移動忽略，手靜止時游標還在飄就調大"),
        ]),
        ("絕對模式", [
            Field("cursor.frame_margin", "畫面留白", "float", 0.0, 0.4, 0.01, "畫面四周留白比例，預覽視窗的藍框就是有效範圍"),
            Field("cursor.smoothing_min_cutoff", "平滑度", "float", 0.05, 5.0, 0.05, "越小越平滑，但游標會比較黏"),
            Field("cursor.smoothing_beta", "快速移動反應", "float", 0.0, 0.2, 0.001, "越大，快速移動時延遲越小"),
        ]),
    ]),
    ("點擊與捏合", [
        ("點擊", [
            Field("control.click_lock_seconds", "點擊時鎖游標（秒）", "float", 0.0, 0.5, 0.01, "捏合瞬間鎖住游標，避免點歪；0 = 不鎖"),
            Field("control.drag_threshold_px", "拖曳門檻（像素）", "float", 5, 100, 1, "捏著移動超過幾像素才算拖曳"),
            Field("control.right_hold_seconds", "右鍵：捏住不動（秒）", "float", 0.2, 2.0, 0.05, "食指捏住不動多久算右鍵"),
        ]),
        ("捏合判定", [
            Field("detection.pinch_enter", "捏合門檻", "float", 0.1, 0.5, 0.01, "越小越難觸發捏合"),
            Field("detection.pinch_exit", "放開門檻", "float", 0.15, 0.7, 0.01, "要比捏合門檻大；越大越不容易誤放開"),
        ]),
        ("手出畫面時", [
            Field("detection.loose_palm", "寬鬆移動判定", "bool", tip="不是握拳、捏合、雙指、三指就當作張開手掌，手指被誤判也能移動（只伸食指也會移動）"),
            Field("detection.edge_hold", "出畫面保持", "bool", tip="手指跑出鏡頭畫面時沿用上一次的狀態，避免手到邊緣突然變握拳或停住"),
        ]),
        ("握拳", [
            Field("control.pause_hold_seconds", "握拳暫停（秒）", "float", 0.5, 5.0, 0.1, "握拳維持多久切換暫停 / 恢復"),
        ]),
    ]),
    ("捲動與搖桿", [
        ("搖桿（中指捏拇指）", [
            Field("control.joystick_max_speed", "最高捲動速度", "float", 5, 100, 1, "每秒最多捲幾格"),
            Field("control.joystick_deadzone", "死區", "float", 0.0, 0.15, 0.005, "離起點不到畫面高的這個比例不捲動"),
            Field("control.joystick_full", "達到最高速的距離", "float", 0.05, 0.5, 0.01, "偏到畫面高的這個比例時捲最快"),
            Field("control.joystick_tap_seconds", "方向鍵：快放（秒）", "float", 0.1, 1.0, 0.05, "捏住不到這麼久就放開 = 方向鍵上 / 下"),
            Field("control.joystick_nav_distance", "翻頁距離", "float", 0.02, 0.3, 0.01, "左右偏超過畫面寬的這個比例，放開時翻頁"),
        ]),
        ("捲動", [
            Field("control.scroll_invert", "反轉捲動方向", "bool"),
            Field("control.scroll_inertia", "甩動慣性", "bool", tip="甩動捲動後頁面會繼續滑動並慢慢停下"),
            Field("control.scroll_inertia_min_speed", "慣性觸發速度", "float", 1, 60, 1, "甩動速度超過每秒幾格才有慣性"),
            Field("control.scroll_inertia_friction", "慣性減速", "float", 0.5, 10, 0.1, "越大停得越快"),
            Field("control.scroll_sensitivity", "移動捲動靈敏度", "float", 5, 150, 1, "scroll 動作用：手移動整個畫面高 = 捲幾格"),
            Field("control.flick_scroll_gain", "甩動捲動力道", "float", 2, 80, 1, "越大一甩捲越多"),
        ]),
        ("三指選單（切換視窗）", [
            Field("control.menu_select_distance", "選格子的移動距離", "float", 0.02, 0.2, 0.005,
                  "手往上下左右移超過畫面的這個比例就選到那格；太容易選到就調大"),
        ]),
    ]),
    ("雙手", [
        ("主控手", [
            Field("detection.control_hand", "主控手", "choice", choices=(("right", "右手"), ("left", "左手"), ("any", "不分左右"))),
            Field("detection.swap_hands", "左右手判斷相反", "bool", tip="預覽視窗手腕旁的 L / R 和實際相反時打勾"),
        ]),
        ("雙手縮放（兩手食指捏拇指拉開 / 靠近）", [
            Field("two_hands.zoom", "啟用縮放", "bool"),
            Field("two_hands.zoom_step", "縮放一格的距離變化", "float", 0.05, 0.5, 0.01, "太敏感就調大"),
        ]),
        ("另一隻手調音量（中指捏拇指上下移）", [
            Field("two_hands.volume", "啟用音量", "bool"),
            Field("two_hands.volume_max_speed", "最快速度", "float", 1, 30, 1, "每秒最多按幾下音量鍵（每下約 2%）"),
            Field("two_hands.volume_deadzone", "死區", "float", 0.0, 0.15, 0.005),
            Field("two_hands.volume_full", "達到最快的距離", "float", 0.05, 0.5, 0.01),
        ]),
    ]),
    ("聲音與顯示", [
        ("提示音", [
            Field("sound.enabled", "暫停 / 恢復提示音", "bool"),
            Field("sound.volume", "提示音音量", "float", 0.0, 1.0, 0.05),
            Field("sound.pause_file", "自訂暫停音效", "file", tip="留空 = 內建低音"),
            Field("sound.resume_file", "自訂恢復音效", "file", tip="留空 = 內建高音"),
            Field("sound.click_enabled", "點擊聲", "bool"),
            Field("sound.click_volume", "點擊聲音量", "float", 0.0, 1.0, 0.05),
            Field("sound.click_file", "自訂點擊音效", "file", tip="留空 = 內建"),
        ]),
        ("游標旁的狀態圓圈", [
            Field("overlay.enabled", "顯示狀態圓圈", "bool"),
            Field("overlay.size", "大小（像素）", "int", 6, 48, 1),
            Field("overlay.offset", "離游標距離（像素）", "int", 0, 60, 1),
        ]),
        ("預覽", [
            Field("show_preview", "顯示鏡頭預覽視窗", "bool"),
            Field("detection.edge_margin", "出畫面提醒範圍", "float", 0.0, 0.15, 0.005, "手離畫面邊緣小於這個比例時圓圈閃黃"),
        ]),
    ]),
    ("鏡頭", [
        ("鏡頭", [
            Field("camera.index", "鏡頭編號", "int", 0, 9, 1, "筆電內建鏡頭通常是 0"),
            Field("camera.width", "寬度", "choice", choices=((320, "320"), (640, "640"), (960, "960"), (1280, "1280"))),
            Field("camera.height", "高度", "choice", choices=((240, "240"), (480, "480"), (540, "540"), (720, "720"))),
            Field("camera.mirror", "左右翻轉畫面", "bool", tip="像照鏡子一樣比較直覺"),
        ]),
    ]),
    ("進階", [
        ("手部辨識", [
            Field("detection.min_detection_confidence", "偵測信心門檻", "float", 0.3, 0.95, 0.05, "越高越不會誤認，但比較容易抓不到手"),
            Field("detection.min_tracking_confidence", "追蹤信心門檻", "float", 0.3, 0.95, 0.05),
            Field("detection.extend_ratio", "手指伸直門檻", "float", 0.9, 1.5, 0.01, "判斷手指是否伸直"),
            Field("control.stable_frames", "手勢確認幀數", "int", 1, 8, 1, "手勢要連續幾幀一致才生效；越大越穩但反應越慢"),
        ]),
        ("甩動判定（手勢動作設為 flick_scroll / flick_windows 才有作用）", [
            Field("control.swipe_min_speed", "甩動速度門檻", "float", 0.3, 4.0, 0.1, "常誤觸就調大"),
            Field("control.swipe_min_distance", "甩動距離門檻", "float", 0.02, 0.3, 0.01, "常誤觸就調大"),
            Field("control.swipe_cooldown", "冷卻時間（秒）", "float", 0.1, 2.0, 0.05, "一次甩動後多久內不再判定"),
        ]),
        ("手掌甩動（手勢動作設為 move_flick_scroll 才有作用）", [
            Field("control.palm_flick_nav", "手掌左右甩翻頁", "bool"),
            Field("control.palm_swipe_min_speed", "手掌甩動速度門檻", "float", 0.5, 6.0, 0.1),
        ]),
    ]),
]


def all_fields() -> List[Field]:
    return [f for _, groups in PAGES for _, items in groups for f in items]


def get_value(cfg: Config, key: str) -> Any:
    if "." not in key:
        return getattr(cfg, key)
    sec, name = key.split(".", 1)
    return getattr(getattr(cfg, sec), name)


def set_value(data: Dict[str, Any], key: str, value: Any) -> None:
    if "." not in key:
        data[key] = value
    else:
        sec, name = key.split(".", 1)
        data.setdefault(sec, {})[name] = value


def config_to_dict(cfg: Config) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for f in all_fields():
        set_value(data, f.key, get_value(cfg, f.key))
    return data


def save_values(path: Path, values: Dict[str, Any]) -> Config:
    """把 {區塊.欄位: 值} 寫進設定檔，回傳檢查過的新設定。格式不對會丟出 ValueError，檔案不變。"""
    import yaml

    text = path.read_text(encoding="utf-8") if path.exists() else ""
    data: Dict[str, Any] = {}
    for key, value in values.items():
        set_value(data, key, value)
    new_text = update_yaml_text(text, data)
    cfg = config_from_dict(yaml.safe_load(new_text))   # 先驗證再寫，避免寫壞設定檔
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    tmp.replace(path)
    return cfg


def _float_decimals(step: float) -> int:
    text = f"{step:.6f}".rstrip("0")
    return max(0, len(text.split(".")[1]) if "." in text else 0)


def build_window(config_path: Path):
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
        QLineEdit, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
    )

    class SettingsWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("手勢滑鼠設定")
            self.resize(560, 640)
            self.path = config_path
            self.cfg = load_config(config_path) if config_path.exists() else Config()
            self.setters: Dict[str, Any] = {}
            self.pending: Dict[str, Any] = {}
            self._loading = False
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(300)   # 拉滑桿時停 0.3 秒才存檔
            self._timer.timeout.connect(self.save)

            tabs = QTabWidget()
            for title, groups in PAGES:
                page = QWidget()
                v = QVBoxLayout(page)
                for gtitle, items in groups:
                    box = QGroupBox(gtitle)
                    form = QFormLayout(box)
                    for f in items:
                        label = f.label + ("（需重開）" if f.restart else "")
                        lab = QLabel(label)
                        w = self._make_editor(f)
                        if f.tip:
                            lab.setToolTip(f.tip)
                            w.setToolTip(f.tip)
                        form.addRow(lab, w)
                    v.addWidget(box)
                v.addStretch(1)
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(page)
                tabs.addTab(scroll, title)

            self.status = QLabel("改了會自動儲存並馬上套用。標「需重開」的項目要重開手勢程式。")
            self.status.setWordWrap(True)
            reset = QPushButton("恢復預設值")
            reset.clicked.connect(self.reset_defaults)
            close = QPushButton("關閉")
            close.clicked.connect(self.close)
            bottom = QHBoxLayout()
            bottom.addWidget(reset)
            bottom.addStretch(1)
            bottom.addWidget(close)

            root = QVBoxLayout(self)
            root.addWidget(tabs)
            root.addWidget(self.status)
            root.addLayout(bottom)
            self.load(self.cfg)

        # ---------- 各種輸入元件 ----------

        def _make_editor(self, f: Field):
            if f.kind == "bool":
                w = QCheckBox()
                w.toggled.connect(lambda v, k=f.key: self.changed(k, bool(v)))
                self.setters[f.key] = lambda v, w=w: w.setChecked(bool(v))
                return w
            if f.kind == "choice":
                w = QComboBox()
                for value, text in f.choices:
                    w.addItem(text, value)
                w.currentIndexChanged.connect(lambda i, k=f.key, w=w: self.changed(k, w.itemData(i)))

                def set_choice(v, w=w, f=f):
                    i = w.findData(v)
                    if i < 0:   # 設定檔裡是清單外的值：照樣顯示
                        w.addItem(str(v), v)
                        i = w.count() - 1
                    w.setCurrentIndex(i)
                self.setters[f.key] = set_choice
                return w
            if f.kind == "file":
                edit = QLineEdit()
                edit.setPlaceholderText("留空 = 內建音效")
                edit.editingFinished.connect(lambda k=f.key, e=edit: self.changed(k, e.text().strip()))
                browse = QPushButton("選擇…")
                clear = QPushButton("清除")

                def pick(_=False, k=f.key, e=edit):
                    name, _ = QFileDialog.getOpenFileName(self, "選擇 wav 音效", "", "WAV 音效 (*.wav)")
                    if name:
                        e.setText(name)
                        self.changed(k, name)

                def wipe(_=False, k=f.key, e=edit):
                    e.setText("")
                    self.changed(k, "")
                browse.clicked.connect(pick)
                clear.clicked.connect(wipe)
                box = QWidget()
                h = QHBoxLayout(box)
                h.setContentsMargins(0, 0, 0, 0)
                h.addWidget(edit, 1)
                h.addWidget(browse)
                h.addWidget(clear)
                self.setters[f.key] = lambda v, e=edit: e.setText(str(v or ""))
                return box

            # 數字：滑桿 + 數字框
            is_int = f.kind == "int"
            scale = 1 if is_int else round(1 / f.step)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(round(f.lo * scale), round(f.hi * scale))
            if is_int:
                spin = QSpinBox()
                spin.setRange(int(f.lo), int(f.hi))
            else:
                spin = QDoubleSpinBox()
                spin.setDecimals(_float_decimals(f.step))
                spin.setRange(f.lo, f.hi)
                spin.setSingleStep(f.step)
            spin.setMinimumWidth(80)

            def from_slider(i, spin=spin):
                spin.setValue(i if is_int else i / scale)

            def from_spin(v, k=f.key, slider=slider):
                slider.blockSignals(True)
                slider.setValue(round(v * scale))
                slider.blockSignals(False)
                self.changed(k, int(v) if is_int else round(float(v), 6))

            slider.valueChanged.connect(from_slider)
            spin.valueChanged.connect(from_spin)

            def set_num(v, spin=spin, slider=slider, f=f):
                # 設定檔的值超出滑桿範圍時放寬範圍，不偷改使用者的值
                if v < spin.minimum() or v > spin.maximum():
                    spin.setRange(min(v, spin.minimum()), max(v, spin.maximum()))
                    slider.setRange(round(spin.minimum() * scale), round(spin.maximum() * scale))
                spin.setValue(v)
                slider.setValue(round(v * scale))
            self.setters[f.key] = set_num

            box = QWidget()
            h = QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(slider, 1)
            h.addWidget(spin)
            return box

        # ---------- 讀寫 ----------

        def load(self, cfg: Config) -> None:
            self._loading = True
            try:
                for f in all_fields():
                    self.setters[f.key](get_value(cfg, f.key))
            finally:
                self._loading = False

        def changed(self, key: str, value: Any) -> None:
            if self._loading:
                return
            self.pending[key] = value
            self._timer.start()

        def save(self) -> bool:
            if not self.pending:
                return True
            values = dict(self.pending)
            # 捏合 / 放開門檻要成對合理
            enter = values.get("detection.pinch_enter", self.cfg.detection.pinch_enter)
            exit_ = values.get("detection.pinch_exit", self.cfg.detection.pinch_exit)
            if exit_ < enter:
                self.status.setText("⚠ 放開門檻要比捏合門檻大，這兩項先不儲存。")
                values.pop("detection.pinch_enter", None)
                values.pop("detection.pinch_exit", None)
            try:
                self.cfg = save_values(self.path, values)
            except Exception as e:
                self.status.setText(f"⚠ 儲存失敗：{e}")
                return False
            for k in values:
                self.pending.pop(k, None)
            needs_restart = [f.label for f in all_fields() if f.key in values and f.restart]
            if needs_restart:
                self.status.setText(f"已儲存。「{'、'.join(needs_restart)}」要重開手勢程式才會生效。")
            elif exit_ >= enter:
                self.status.setText("已儲存並套用。")
            return True

        def reset_defaults(self) -> None:
            ok = QMessageBox.question(self, "恢復預設值", "所有數值都改回預設值？（手勢對應的動作不會變）")
            if ok != QMessageBox.Yes:
                return
            self._timer.stop()
            self.pending.clear()
            defaults = Config()
            self.load(defaults)
            try:
                self.cfg = save_values(self.path, {f.key: get_value(defaults, f.key) for f in all_fields()})
                self.status.setText("已恢復預設值。鏡頭等標「需重開」的項目要重開手勢程式才會生效。")
            except Exception as e:
                self.status.setText(f"⚠ 儲存失敗：{e}")

        def closeEvent(self, event) -> None:
            self._timer.stop()
            self.save()
            event.accept()

    return SettingsWindow()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="手勢滑鼠設定視窗")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="設定檔路徑（預設為專案根目錄的 config.yaml）")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("設定視窗需要 PySide6，請執行：pip install -r requirements.txt")
        sys.exit(1)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    win = build_window(args.config)
    win.show()
    win.raise_()
    win.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
